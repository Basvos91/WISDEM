#-------------------------------------------------------------------------------
# Name:        Tube.py
# Purpose: This module contains the tube class, which calculates structural
#          properties of a hollow, uniform, cylindrical beam
#
# Author:      rdamiani
#
# Created:     04/11/2013
# Copyright:   (c) rdamiani 2013
# Licence:     <your licence>
#-------------------------------------------------------------------------------
from __future__ import print_function
import math
import numpy as np
from .Material import Material
from openmdao.api import ExplicitComponent, Group, Problem
from wisdem.commonse.utilities import nodal2sectional
pi = math.pi

def main():
    print('Testing Tube')
    a=Tube(np.array([5.,6.]),np.array([0.10,0.10]),np.array([10.,10]),mat=Material(matname='heavySteel'))
    print('Area and PSEUDOMass of tube a', a.Area, a.pseudomass)
    b=Tube(3.,0.10,10.,mat=Material(matname='heavySteel'))
    print('Area and PSEUDOMass of tube b', b.Area, b.pseudomass)



class CylindricalShellProperties(ExplicitComponent):
    """
    OpenMDAO wrapper for tube class to obtain cylindrical sheel properties.
    
    Parameters
    ----------
    d : numpy array[nFull]
        tower diameter at corresponding locations
    t : numpy array[nFull-1]
        shell thickness at corresponding locations
    
    Returns
    -------
    Az : numpy array[nFull-1]
        cross-sectional area
    Asx : numpy array[nFull-1]
        x shear area
    Asy : numpy array[nFull-1]
        y shear area
    Jz : numpy array[nFull-1]
        polar moment of inertia
    Ixx : numpy array[nFull-1]
        area moment of inertia about x-axis
    Iyy : numpy array[nFull-1]
        area moment of inertia about y-axis
    
    """
    def initialize(self):
        self.options.declare('nFull')
        
    def setup(self):
        nFull = self.options['nFull']

        self.add_input('d', np.zeros(nFull), units='m')
        self.add_input('t', np.zeros(nFull-1), units='m')

        self.add_output('Az', np.zeros(nFull-1), units='m**2')
        self.add_output('Asx', np.zeros(nFull-1), units='m**2')
        self.add_output('Asy', np.zeros(nFull-1), units='m**2')
        self.add_output('Jz', np.zeros(nFull-1), units='m**4')
        self.add_output('Ixx', np.zeros(nFull-1), units='m**4')
        self.add_output('Iyy', np.zeros(nFull-1), units='m**4')

        # Derivatives
        self.declare_partials('*', '*', method='fd', form='central', step=1e-6)

    def compute(self, inputs, outputs):
        d,_ = nodal2sectional(inputs['d'])
        tube = Tube(d,inputs['t'])

        outputs['Az'] = tube.Area
        outputs['Asx'] = tube.Asx
        outputs['Asy'] = tube.Asy
        outputs['Jz'] = tube.J0
        outputs['Ixx'] = tube.Jxx
        outputs['Iyy'] = tube.Jyy

class Tube:
    """The Tube Class contains functions to calculate properties of tubular circular cross-sections
    for structural analyses. It assumes 1 material specification, even though I may pass
    more than 1 element (D's,L's,Kbuck's, and t's) to the class."""
    def __init__(self, D, t, Lgth=np.NaN, Kbuck=1., mat=Material(name='ASTM992 steel')):
        self.D=D
        self.t=t
        self.L=Lgth*np.ones(np.size(D)) #this makes sure we exapnd Lght if D,t, arrays
        self.Kbuck=Kbuck*np.ones(np.size(D)) #this makes sure we exapnd Kbuck if D,t, arrays
        self.mat=mat
        if np.size(D)>1 and type(mat) != np.ndarray: #in this case I need to make sure we have a list of materials
            import copy
            self.mat=np.array([copy.copy(mat) for i in range(np.size(D))])

    @property
    def Area(self): #Cross sectional area of tube
        return (self.D**2-(self.D-2*self.t)**2)* pi/4

    @property
    def derivArea(self):
        return {'D': 2* pi/4 * (self.D**2-(self.D-2*self.t)) * (2*self.D -1),
                't': 0}

    @property
    def Amid(self): #mid-thickness inscribed area of tube (thin wall torsion calculation)
        return (self.D-self.t)**2* pi/4

    @property
    def Jxx(self): #2nd area moment of inertia w.r.t. x-x axis (Jxx=Jyy for tube)
        return (self.D**4-(self.D-2*self.t)**4)* pi/64

    @property
    def Jyy(self): #2nd area moment of inertia w.r.t. x-x axis (Jxx=Jyy for tube)
        return self.Jxx

    @property
    def J0(self):  #polar moment of inertia w.r.t. z-z axis (torsional)
        return (2.0 * self.Jxx)

    @property
    def Asy(self): #Shear Area for tubular cross-section
        Ri=self.D/2-self.t
        Ro=self.D/2
        return self.Area / ( 1.124235 + 0.055610*(Ri/Ro) + 1.097134*(Ri/Ro)**2 - 0.630057*(Ri/Ro)**3 )

    @property
    def Asx(self): #Shear Area for tubular cross-section
        return self.Asy

    @property
    def BdgMxx(self):  #Bending modulus for tubular cross-section
        return self.Jxx / (self.D/2)

    @property
    def BdgMyy(self):  #Bending modulus for tubular cross-section =BdgMxx
        return self.Jyy / (self.D/2)

    @property
    def TorsConst(self):  #Torsion shear constant for tubular cross-section
        return self.J0 / (self.D/2)

    @property
    def S(self):  #Bending modulus for tubular cross-section
        return self.BdgMxx

    @property
    def C(self):  #Torsion shear constant for tubular cross-section
        return self.TorsConst

    @property
    def Rgyr(self): #Radius of Gyration for circular tube
        return np.sqrt(self.Jxx/self.Area)

    @property
    def Klr(self): #Klr buckling parameter
        return self.Kbuck*self.L/self.Rgyr

    @property
    def pseudomass(self): #This uses the buckling length as actual length, !!!CAUTION!!!!!!
        pseudomass =0. #initialize

        if np.size(self.D)>1:
            for ii,mat in enumerate(self.mat):
                    pseudomass +=self.Area*self.L*mat.rho
        else:
            pseudomass =(self.Area*self.L*self.mat.rho)
        return pseudomass


if __name__ == '__main__':
    main()
