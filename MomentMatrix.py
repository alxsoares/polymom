#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
"""
classes and helper moment matrices and localizing matrices,
which takes contraints as input produce the right outputs
for the cvxopt SDP solver

Sketchy: tested using sympy 0.7.6 (the default distribution did not work)
and cvxopt
"""

#from __future__ import division
import sympy as sp
import numpy as np

import sympy.polys.monomials as mn
from sympy.polys.orderings import monomial_key

import scipy.linalg

from collections import defaultdict
import util
import ipdb
from cvxopt import matrix, sparse, spmatrix

def monomial_filter(mono, filter='even', debug=False):
        if filter is 'even':
            if debug and not mono==1:
                print str(mono) + ':\t' + str(all([(i%2)==0 for i in mono.as_poly().degree_list()]))
            return 1 if mono==1 else int(all([i%2==0 for i in mono.as_poly().degree_list()]))

def dict_mono_to_ind(monolist):
    dict = {}
    for i,mono in enumerate(monolist):
        dict[mono]=i
    return dict

def solve_moments_with_constraints(symbols, constraints, deg):
    """
    Solve using the moment matrix.
    Use @symbols with basis bounded by degree @deg.
    Also use the constraints.
    """
    from cvxopt import solvers
    M = MomentMatrix(deg, symbols, morder='grevlex')
    cin = M.get_cvxopt_inputs(constraints)
    sol = solvers.sdp(cin['c'], Gs=cin['G'], hs=cin['h'], A=cin['A'], b=cin['b'])

    return M, sol

class MomentMatrix(object):
    """
    class to handle moment matrices and localizing matrices, and to
    produce the right outputs for the cvxopt SDP solver degree: max
    degree of the basic monomials corresponding to each row, so the
    highest degree monomial in the entire moment matrix would be twice
    the provided degree.
    """
    def __init__(self, degree, variables, morder='grevlex'):
        """
        @param degree - highest degree of the first row/column of the
        moment matrix
        @param variables - list of sympy symbols
        """
        self.degree = degree
        self.vars = variables
        self.num_vars = len(self.vars)

        # this object is a list of all monomials
        # in num_vars variables up to degree degree
        rawmonos = mn.itermonomials(self.vars, self.degree)

        # the reverse here is a bit random..., but has to be done
        self.row_monos = sorted(rawmonos,\
                                 key=monomial_key(morder, self.vars[::-1]))
        
        # This list correspond to the actual variables in the sdp solver
        # probably better to generate this from row_monos rather than this...
        self.matrix_monos = sorted(mn.itermonomials(self.vars, 2*self.degree),\
                                   key=monomial_key(morder, self.vars[::-1]))

        self.num_matrix_monos = len(self.matrix_monos)

        self.expanded_monos = []
        for yi in self.row_monos:
            for yj in self.row_monos:
                self.expanded_monos.append(yi*yj)

        # mapping from a monomial to a list of indices of
        # where the monomial appears in the moment matrix
        self.term_to_indices_dict = defaultdict(list)
        for i,yi in enumerate(self.expanded_monos):
            self.term_to_indices_dict[yi].append(i)

    def __str__(self):
        return 'moment matrix for %d variables: %s' % (self.num_vars, str(self.vars))

    def __get_rowofA(self, constr):
        """
        @param - constr is a polynomial constraint expressed as a sympy
        polynomial. constr is h_j in Lasserre's notation,
        and represents contraints on entries of the moment matrix.
        """
        Ai = np.zeros(self.num_matrix_monos)
        coefdict = constr.as_coefficients_dict();
        # you can build a dict and do this faster, but no point since we solve SDP later
        for i,yi in enumerate(self.matrix_monos):
            Ai[i] = coefdict.get(yi,0)
        return Ai
    
    def __get_indicators_lists(self):
        allconstraints = []
        for yi in self.matrix_monos:
            indices = self.term_to_indices_dict[yi]
            allconstraints += [spmatrix(-1,[0]*len(indices), indices, size=(1,len(self.expanded_monos)), tc='d')]
        return allconstraints
    
    def get_cvxopt_inputs(self, constraints = None, sparsemat = True, filter = 'even'):
        """
        if provided, constraints should be a list of sympy polynomials that should be 0.

        """
        
        # Many for what c might be, not yet determined really
        if filter is None:
            c = matrix(np.ones((self.num_matrix_monos, 1)))
        else:
            c = matrix([monomial_filter(yi, filter='even') for yi in self.matrix_monos], tc='d')
            
        num_constrs = len(constraints) if constraints is not None else 0
        
        Anp = np.zeros((num_constrs+1, self.num_matrix_monos))
        bnp = np.zeros((num_constrs+1,1))
        if constraints is not None:
            for i,constr in enumerate(constraints):
                Anp[i,:] = self.__get_rowofA(constr)
        
        Anp[-1,0] = 1
        bnp[-1] = 1
        b = matrix(bnp)

        if sparsemat:
            G = [sparse(self.__get_indicators_lists(), tc='d').trans()]
            A = sparse(matrix(Anp))
        else:
            G = [matrix(self.__get_indicators_lists(), tc='d').trans()]
            A = matrix(Anp)
        num_row_monos = len(self.row_monos)
        h = [matrix(np.zeros((num_row_monos,num_row_monos)))]    
        
        return {'c':c, 'G':G, 'h':h, 'A':A, 'b':b}

    def numeric_instance(self, vals):
        """
        assign the matrix_monos vals and return an np matrix
        """
        assert(len(vals)==len(self.matrix_monos))
        
        G = self.__get_indicators_lists()
        num_inst = np.zeros(len(self.row_monos)**2)
        for i,val in enumerate(vals):
            num_inst += -val*np.array(matrix(G[i])).flatten()
        num_row_monos = len(self.row_monos)
        return num_inst.reshape(num_row_monos,num_row_monos)
        
    def extract_solutions_lasserre(self, vals, Kmax=10, tol=1e-5):
        """
        extract solutions via (unstable) row reduction described by Lassarre and used in gloptipoly
        """
        M = self.numeric_instance(vals)
        Us,Sigma,Vs=np.linalg.svd(M)
        #
        #ipdb.set_trace()
        count = min(Kmax,sum(Sigma>tol))
        # now using Lassarre's notation in the extraction section of
        # "Moments, Positive Polynomials and their Applications"
        T,Ut = util.srref(Vs[0:count,:])
        print 'the next biggest eigenvalue we are losing is %f' % Sigma[count]
        # inplace!
        util.row_normalize_leadingone(Ut)
        
        couldbes = np.where(Ut>0.9)
        ind_leadones = np.zeros(Ut.shape[0], dtype=np.int)
        for j in reversed(range(len(couldbes[0]))):
            ind_leadones[couldbes[0][j]] = couldbes[1][j]
        
        basis = [self.row_monos[i] for i in ind_leadones]
        dict_row_monos = dict_mono_to_ind(self.row_monos)
        
        #ipdb.set_trace()
        Ns = {}
        bl = len(basis)
        # create multiplication matrix for each variable
        for var in self.vars:
            Nvar = np.zeros((bl,bl))
            for i,b in enumerate(basis):
                Nvar[:,i] = Ut[ :,dict_row_monos[var*b] ]
            Ns[var] = Nvar

        N = np.zeros((bl,bl))
        for var in Ns:
            N+=Ns[var]*np.random.randn()
        T,Q=scipy.linalg.schur(N)

        sols = {}
        
        quadf = lambda A, x : np.dot(x, np.dot(A,x))
        for var in self.vars:
            sols[var] = [quadf(Ns[var], Q[:,j]) for j in range(bl)]
        #ipdb.set_trace()
        return sols
        


class LocalizingMatrix(object):
    '''
    poly_g is a polynomial that multiplies termwise with a basic
    moment matrix of smaller size to give the localizing matrices This
    class depends on the moment matrix class and has exactly the same
    monomials as the base moment matrix. So the SDP variables still
    corresponds to matrix_monos
    '''

    def __init__(self, mm, poly_g, morder='grevlex'):
        """
        @param - mm is a MomentMatrix object
        @param - poly_g the localizing polynomial
        """
        self.mm = mm
        self.poly_g = poly_g
        self.deg_g = poly_g.as_poly().total_degree()
        #there is no point to a constant localization matrix,
        #and it will cause crash because how sympy handles 1
        assert(self.deg_g>0)         
        rawmonos = mn.itermonomials(self.mm.vars, self.mm.degree-self.deg_g);
        self.row_monos = sorted(rawmonos,\
                                 key=monomial_key(morder, mm.vars[::-1]))
        self.expanded_polys = [];
        for yi in self.row_monos:
            for yj in self.row_monos:
                self.expanded_polys.append(sp.expand(poly_g*yi*yj))
        # mapping from a monomial to a list of indices of
        # where the monomial appears in the moment matrix
        self.term_to_indices_dict = defaultdict(list)
        for i,pi in enumerate(self.expanded_polys):
            coeffdict = pi.as_coefficients_dict()
            for mono in coeffdict:
                coeff = coeffdict[mono]
                self.term_to_indices_dict[mono].append( (i,float(coeff)) )
        
    def __get_indicators_list(self):
        """
        @param - polynomial here is called g in Lasserre's notation
        and defines the underlying set K some parallel with
        MomentMatrix.__get_indicators_list. Except now expanded_monos becomes
        expanded_polys
        """
        allconstraints = []
        for yi in self.mm.matrix_monos:
            indices = [k for k,v in self.term_to_indices_dict[yi]]
            values = [-v for k,v in self.term_to_indices_dict[yi]]
            allconstraints += [spmatrix(values, [0]*len(indices), \
                                        indices, size=(1,len(self.expanded_polys)), tc='d')]
        return allconstraints

    def get_cvxopt_Gh(self, sparsemat = True):
        """
        get the G and h corresponding to this localizing matrix

        """
        
        if sparsemat:
            G = sparse(self.__get_indicators_list(), tc='d').trans()
        else:
            G = matrix(self.__get_indicators_list(), tc='d').trans()

        num_rms = len(self.row_monos)
        h = matrix(np.zeros((num_rms, num_rms)))
        
        return {'G':G, 'h':h}

if __name__=='__main__':
    # simple test to make sure things run
    from cvxopt import solvers
    print 'testing simple unimixture with a skipped observation, just to test that things run'
    x = sp.symbols('x')
    M = MomentMatrix(3, [x], morder='grevlex')
    constrs = [x-1.5, x**2-2.5, x**4-8.5]
    cin = M.get_cvxopt_inputs(constrs)

    gs = [3-x, 3+x]
    locmatrices = [LocalizingMatrix(M, g) for g in gs]
    Ghs = [lm.get_cvxopt_Gh() for lm in locmatrices]

    Gs=cin['G'] + [Gh['G'] for Gh in Ghs]
    hs=cin['h'] + [Gh['h'] for Gh in Ghs]
    
    sol = solvers.sdp(cin['c'], Gs=cin['G'], \
                  hs=cin['h'], A=cin['A'], b=cin['b'])

    print sol['x']
    print abs(sol['x'][3]-4.5)
    assert(abs(sol['x'][3]-4.5) <= 1e-5)
    print M.extract_solutions_lasserre(sol['x'], Kmax = 2)
    print 'true values are 1 and 2'
