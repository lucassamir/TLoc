from ase.io import read, write
from ase.visualize import view
from ase.neighborlist import natural_cutoffs, NeighborList
from scipy import sparse
import numpy as np
import os
from ase.io.trajectory import Trajectory

def find_structure_file(folder):
    """Searches the current working directory for the molecular structure file. 
        Allowed file types are .cif, .gen, .sdf, or .xyz. 

    Args:
        folder (str): The current working directory.

    Returns:
        str: Molecular structure file. 
    """
    import glob
    
    structure_file = glob.glob(folder + '/*.cif') + \
          glob.glob(folder + '/*.gen') + \
          glob.glob(folder + '/*.sdf') + \
          glob.glob(folder + '/*.xyz')
    print(structure_file)
    structure_file = structure_file[0]

    return structure_file

def compute_total_weight(centers_of_mass):
    total_weight = 0
    for i in range(len(centers_of_mass)):
        for j in range(i+1, len(centers_of_mass)):
            total_weight +=  np.linalg.norm(centers_of_mass[i] - centers_of_mass[j])
    return total_weight

def get_centers_of_mass(atoms, n_components, component_list):
    centers_of_mass = []
    for i in range(n_components):
        molIdx_i = component_list[i]
        molIdxs_i = [ x for x in range(len(component_list)) if component_list[x] == molIdx_i ]
        centers_of_mass.append(atoms[molIdxs_i].get_center_of_mass())
    return centers_of_mass

def unwrap_atoms(structure_file=None, write_traj=False):
    if write_traj:
        traj_writer = Trajectory('traj.traj','w')
    folder = os.getcwd()

    if structure_file:
        if os.path.exists(folder + '/../' + structure_file):
            structure_file = folder + '/../' + structure_file
        else:
            structure_file = folder + '/' + structure_file
    else:
        structure_file = find_structure_file(folder)

    atoms = read(structure_file)
    neighbor_list = NeighborList(natural_cutoffs(atoms), self_interaction=False, bothways=True)
    neighbor_list.update(atoms)
    matrix = neighbor_list.get_connectivity_matrix(neighbor_list.nl)
    n_components, component_list = sparse.csgraph.connected_components(matrix)
    idx = 0
    molIdx = component_list[idx]
    print("There are {} molecules in the system".format(n_components))
    molIdxs = [ i for i in range(len(component_list)) if component_list[i] == molIdx ]
    print("The following atoms are part of molecule {}: {}".format(molIdx, molIdxs))
    edges = list(matrix.keys())
    max_bond_len = max(natural_cutoffs(atoms))
    cell = list(atoms.get_cell())
    new_atoms = read(structure_file)
    new_atoms.set_pbc([False,False,False])
    if write_traj:
        traj_writer.write(new_atoms)
    all_positions = new_atoms.get_positions()
    is_optimized = False
    # For each bond, take the lower left and move it upper right until the bond shrinks
    iterations = 0
    print("optimizing atoms")
    while not is_optimized:
        iterations += 1
        print("{} iterations".format(iterations))
        is_optimized = True
        for i in range(3):
            for edge in edges:
                positions = all_positions
                distance = np.linalg.norm(positions[edge[0]]-positions[edge[1]])
                if distance > max_bond_len*2:
                    min_pos = positions[edge[0]] if positions[edge[0],i] < positions[edge[1],i] else positions[edge[1]]
                    max_pos = positions[edge[0]] if positions[edge[0],i] >= positions[edge[1],i] else positions[edge[1]]
                    new_pos = min_pos
                    if np.linalg.norm(max_pos - (min_pos + cell[i])) < distance:
                        new_pos = min_pos + cell[i]
                        is_optimized = False
                    if np.array_equal(min_pos,positions[edge[0]]):
                        all_positions[edge[0]] = new_pos
                        all_positions[edge[1]] = max_pos
                    else:
                        all_positions[edge[0]] = max_pos
                        all_positions[edge[1]] = new_pos
                    if write_traj:
                        new_atoms.set_positions(all_positions)
                        traj_writer.write(new_atoms)
    new_atoms.set_positions(all_positions)

    # Construct graph (compute total weight)
    original_centers_of_mass = get_centers_of_mass(new_atoms, n_components, component_list)
    centers_of_mass = np.copy(original_centers_of_mass)
    weight = compute_total_weight(centers_of_mass)
    test_dirs = cell
    test_dirs.extend([-x for x in test_dirs])

    is_optimized = False
    while not is_optimized:
        is_optimized = True
        for i in range(n_components):
            for j in range(6):
                test_centers_of_mass = np.copy(centers_of_mass)
                test_centers_of_mass[i] += test_dirs[j]
                test_weight = compute_total_weight(test_centers_of_mass)
                if test_weight < weight:
                    centers_of_mass = np.copy(test_centers_of_mass)
                    weight = test_weight
                    is_optimized = False
    translations = np.zeros([len(new_atoms), 3])
    
    for i in range(n_components):
        molIdx = component_list[i]
        molIdxs = [ x for x in range(len(component_list)) if component_list[x] == molIdx ]
        
        dif = centers_of_mass[i] - original_centers_of_mass[i]
        translations[molIdxs,:] = dif

    new_atoms.translate(translations)
    new_atoms.center()
    if write_traj:
        traj_writer.write(new_atoms)
    write("structure.xyz", new_atoms)

unwrap_atoms("tloc/tests/rubrene.cif")