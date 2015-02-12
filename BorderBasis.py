#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
"""
Constructing border bases
"""

import numpy as np
import sympy as sp
from numpy import array, zeros, atleast_2d, hstack, diag
from numpy.linalg import norm, svd, qr

from sympy import ring, RR, lex, grevlex, pprint
from util import *
from itertools import chain

#from MonomialSpan import MonomialSpan, approximate_unitary
from ComputationalUniverse import BorderBasedUniverse, DegreeBoundedUniverse

class Basis(object):
    """
    A basis supports some basis functionalities of quotienting and division.
    """

    def __init__(self, L, R, generators):
        """
        @param L - computational universe
        @param generators - Generators of the basis
        """
        self.L = L 
        self.__generators = generators

    @property
    def generator_basis(self):
        """
        Return generators basis
        """
        return self.__generators

    @property
    def quotient_basis(self):
        """
        Return quotient basis
        """

        raise NotImplementedError()

    def quotient(self, f):
        """
        Find the quotient of f mod I.
        """

        raise NotImplementedError()

    def multiplication_matrix(self, f):
        """
        Return the characteristic multiplication matrix of f.
        """
        return self.L.vector_space([self.quotient(f * b)
            for b in self.quotient_basis()])

    def formal_multiplication_matrices(self):
        """
        Construct the multiplication matrices for each symbol
        """
        return [self.multiplication_matrix(sym) for sym in self.L.symbols]

    def zeros(self):
        """
        Find the zeros of the ideal by the companion method.
        """
        Ms = self.formal_multiplication_matrices()
        # Simultaneously diagonalize
        L, _ = simultaneously_diagonalize(Ms)
        return zip(*L)

class BorderBasis(Basis):
    """
    A border basis.
    """

    def find_basis_nearest_lt(self, t):
        """
        Find the basis element with the nearest leading term
        """
        raise NotImplementedError()


    def find_basis_with_lt(self, t):
        """
        Find the basis element with leading term
        """
        raise NotImplementedError()

    def quotient(self, f):
        raise NotImplementedError()

class BorderBasisFactory(object):
    """
    Creates a border basis
    """

    def __init__(self, delta = eps, order = grevlex):
        self.delta = delta
        self.order = order

    def __final_reduction(self, L, V, O): 
        """
        The final reduction algorithm ensures that each term in the
        border is uniquely associated with each term in basis V
        @params: L - computation universe
        @params: V - O pre-basis
        @params: O - order ideal
        """
        assert len(O) > 0

        # Ensure we are in rref.
        _, V = srref(V, self.delta)
        # set leading coefficients to be 1
        V = lt_normalize(V)
        return O, V

    def __inner_loop(self, L, V):
        """
        Inner loop: Find the L-stable span of V. If B be the
        supplementary space, terminate if $B⁺ ⊆ L$, otherwise, recurse
        with $L⁺$.
        """
        # Get the stable extension
        V = L.stable_extension(V)

        B = L.supplementary_space(V) 
        # Check if we've reached fixed point.
        if not L.contains_extension(B):
            # TODO: An optimization is to extend L by the terms in B.
            return self.__inner_loop(L.extend(), V)
        else:
            return L, V, B

    def generate(self, R, I):
        """
        Return a border basis for fs.
        """

        # Get the computation universe.
        L = DegreeBoundedUniverse.from_support(R, I, tau=self.delta)
        # Get a linear basis for I
        V = L.vector_space(I)
        _, V = srref(V, self.delta)
        L, V, O = self.__inner_loop(L, V)

        # Final reduction
        O, V = self.__final_reduction(L, V, O)
        return L, O, V

