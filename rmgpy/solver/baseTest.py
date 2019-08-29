#!/usr/bin/env python
# -*- coding: utf-8 -*-

###############################################################################
#                                                                             #
# RMG - Reaction Mechanism Generator                                          #
#                                                                             #
# Copyright (c) 2002-2019 Prof. William H. Green (whgreen@mit.edu),           #
# Prof. Richard H. West (r.west@neu.edu) and the RMG Team (rmg_dev@mit.edu)   #
#                                                                             #
# Permission is hereby granted, free of charge, to any person obtaining a     #
# copy of this software and associated documentation files (the 'Software'),  #
# to deal in the Software without restriction, including without limitation   #
# the rights to use, copy, modify, merge, publish, distribute, sublicense,    #
# and/or sell copies of the Software, and to permit persons to whom the       #
# Software is furnished to do so, subject to the following conditions:        #
#                                                                             #
# The above copyright notice and this permission notice shall be included in  #
# all copies or substantial portions of the Software.                         #
#                                                                             #
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR  #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,    #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER      #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING     #
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER         #
# DEALINGS IN THE SOFTWARE.                                                   #
#                                                                             #
###############################################################################

import os.path
import pickle
import unittest

import rmgpy
from rmgpy.rmg.settings import ModelSettings, SimulatorSettings
from rmgpy.tools.loader import loadRMGPyJob


class ConcentrationPrinter(object):
    def __init__(self):
        self.species_names = []
        self.data = []

    def update(self, subject):
        self.data.append((subject.t, subject.coreSpeciesConcentrations))


class ReactionSystemTest(unittest.TestCase):

    def setUp(self):
        self.listener = ConcentrationPrinter()

        folder = os.path.join(os.path.dirname(rmgpy.__file__), 'solver/files/listener/')
        input_file = os.path.join(folder, 'input.py')
        chemkin_file = os.path.join(folder, 'chemkin/chem.inp')
        spc_dict = os.path.join(folder, 'chemkin/species_dictionary.txt')

        self.rmg = loadRMGPyJob(input_file, chemkin_file, spc_dict, generateImages=False, checkDuplicates=False)

    def testSurfaceInitialization(self):
        """
        test that initialize_surface is correctly removing species and reactions when
        they are no longer consistent with the surface (due to other species/reactions moving to the 
        bulk core)
        """
        reaction_system = self.rmg.reactionSystems[0]
        reaction_system.attach(self.listener)
        reaction_model = self.rmg.reactionModel

        core_species = reaction_model.core.species
        core_reactions = reaction_model.core.reactions
        surface_species = [core_species[7], core_species[6]]
        surface_reactions = [core_reactions[0], core_reactions[2], core_reactions[3]]

        reaction_system.initializeModel(core_species, core_reactions,
                                        reaction_model.edge.species, reaction_model.edge.reactions, surface_species,
                                        surface_reactions)

        self.assertEquals(len(surface_species), 1)  # only H should be left
        self.assertEquals(len(surface_reactions), 2)  # all the reactions with H should stay

    def testSurfaceLayeringConstraint(self):
        """
        test that the correct maximum under the surface layering constraint is being
        found
        """
        reaction_system = self.rmg.reactionSystems[0]
        reaction_system.attach(self.listener)
        reaction_model = self.rmg.reactionModel
        core_species = reaction_model.core.species
        core_reactions = reaction_model.core.reactions

        edge_species = [core_species[6], core_species[7]]
        edge_reactions = core_reactions[1:]
        surface_species = [core_species[5]]
        surface_reactions = [core_reactions[0]]
        core_species = core_species[0:6] + [core_species[8]]
        core_reactions = surface_reactions[:]
        reaction_system.numCoreReactions = 1
        reaction_system.numCoreSpecies = 7

        reaction_system.initializeModel(core_species, core_reactions,
                                        edge_species, edge_reactions, surface_species, surface_reactions)

        self.assertEquals(len(reaction_system.surfaceSpeciesIndices), 1)  # surfaceSpeciesIndices calculated correctly
        self.assertEquals(reaction_system.surfaceSpeciesIndices[0], 5)  # surfaceSpeciesIndices calculated correctly

        inds = reaction_system.getLayeringIndices()

        self.assertEquals(inds[0], 1)  # worked correctly
        self.assertEquals(inds[1], 2)

    def testAddReactionsToSurface(self):
        """
        Test that addReactionsToSurface gives the correct surface_species and surface_reactions lists after being called
        """
        reaction_system = self.rmg.reactionSystems[0]
        reaction_system.attach(self.listener)
        reaction_model = self.rmg.reactionModel
        species = reaction_model.core.species
        reactions = reaction_model.core.reactions

        core_species = species[0:6]
        core_reactions = [reactions[0]]
        surface_species = []
        surface_reactions = []
        edge_species = species[6:]
        edge_reactions = reactions[1:]

        reaction_system.initializeModel(core_species, core_reactions,
                                        edge_species, edge_reactions, surface_species, surface_reactions)

        new_surface_reactions = edge_reactions
        new_surface_reaction_inds = [edge_reactions.index(i) for i in new_surface_reactions]

        surface_species, surface_reactions = reaction_system.addReactionsToSurface(
            new_surface_reactions, new_surface_reaction_inds, surface_species, surface_reactions, edge_species)

        self.assertEqual(set(surface_species), set(edge_species))  # all edge species should now be in the surface
        self.assertEqual(set(surface_reactions), set(edge_reactions))  # all edge reactions should now be in the surface

    def testAttachDetach(self):
        """
        Test that a ReactionSystem listener can be attached/detached.
        """
        # create observable

        reaction_system = self.rmg.reactionSystems[0]
        reaction_system.attach(self.listener)
        self.assertNotEqual(reaction_system._observers, [])

        reaction_system.detach(self.listener)
        self.assertEquals(reaction_system._observers, [])

    def testListen(self):
        """
        Test that data can be retrieved from an attached ReactionSystem listener.
        """
        # create observable
        reaction_system = self.rmg.reactionSystems[0]
        reaction_system.attach(self.listener)

        reaction_model = self.rmg.reactionModel

        self.assertEqual(self.listener.data, [])

        model_settings = ModelSettings(toleranceMoveToCore=1, toleranceKeepInEdge=0, toleranceInterruptSimulation=1)
        simulator_settings = SimulatorSettings()

        # run simulation:
        terminated, resurrected, obj, sspcs, srxns, t, conv = reaction_system.simulate(
            coreSpecies=reaction_model.core.species,
            coreReactions=reaction_model.core.reactions,
            edgeSpecies=reaction_model.edge.species,
            edgeReactions=reaction_model.edge.reactions,
            surfaceSpecies=[],
            surfaceReactions=[],
            modelSettings=model_settings,
            simulatorSettings=simulator_settings,
        )

        self.assertNotEqual(self.listener.data, [])

    def testPickle(self):
        """
        Test that a ReactionSystem object can be un/pickled.
        """
        rxn_sys1 = self.rmg.reactionSystems[0]
        rxn_sys = pickle.loads(pickle.dumps(rxn_sys1))

        self.assertIsNotNone(rxn_sys)
        self.assertTrue(isinstance(rxn_sys, rmgpy.solver.simple.SimpleReactor))
        self.assertEqual(rxn_sys.T.value_si, rxn_sys1.T.value_si)
        self.assertEqual(rxn_sys.P.value_si, rxn_sys1.P.value_si)
        self.assertEqual(rxn_sys.termination[0].conversion, rxn_sys1.termination[0].conversion)
        self.assertEqual(rxn_sys.termination[1].time.value_si, rxn_sys1.termination[1].time.value_si)


if __name__ == '__main__':
    unittest.main()
