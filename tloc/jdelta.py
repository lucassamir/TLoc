import numpy as np
from ase.calculators.gaussian import Gaussian
from ase.io import read
from shutil import copyfile
from tloc.javerage import get_orbitals, catnip
from tloc import chdir, mkdir

def get_displacements(atoms, all=True):
    if all:
        latoms = len(atoms)
    else:
        latoms = len(atoms) / 2
    for ia in range(latoms):
        for iv in range(3):
            for sign in [-1, 1]:
                yield (ia, iv, sign)

def displace_atom(atoms, ia, iv, sign, delta):
    new_atoms = atoms.copy()
    pos_av = new_atoms.get_positions()
    pos_av[ia, iv] += sign * delta
    new_atoms.set_positions(pos_av)
    return new_atoms

def finite_dif(delta=0.01, all=True):
    atoms = read('static.xyz')
    for ia, iv, sign in get_displacements(atoms, all=all):
        prefix = 'dj-{}-{}{}{}' .format(int(delta * 1000), 
                                        ia,
                                        'xyz'[iv],
                                        ' +-'[sign])
        new_structure = displace_atom(atoms, ia, iv, sign, delta)
        get_orbitals(new_structure, prefix)

def derivative(jpp, jp, jm, jmm, delta):
    return (-jpp + 8 * jp - 8 * jm + jmm) / 6 * delta

def get_dj_matrix(jlists, delta):
    latoms = len(jlists[0]) / 6

    # array with j + full delta (j plus plus)
    jpp = np.empty([latoms, 3])
    jpp[:, 0] = jlists[1][1::6]
    jpp[:, 1] = jlists[1][3::6]
    jpp[:, 2] = jlists[1][5::6]

    # array with j + half delta (j plus)
    jp = np.empty([latoms, 3])
    jp[:, 0] = jlists[0][1::6]
    jp[:, 1] = jlists[0][3::6]
    jp[:, 2] = jlists[0][5::6]
    
    # array with j - half delta (j minus)
    jm = np.empty([latoms, 3])
    jm[:, 0] = jlists[0][0::6]
    jm[:, 1] = jlists[0][2::6]
    jm[:, 2] = jlists[0][4::6]

    # array with j - full delta (j minus minus)
    jmm = np.empty([latoms, 3])
    jmm[:, 0] = jlists[1][0::6]
    jmm[:, 1] = jlists[1][2::6]
    jmm[:, 2] = jlists[1][4::6]

    dj_matrix = derivative(jpp, jp, jm, jmm, delta)

    return dj_matrix

def get_fluctuations(dj_av, phonons, temp):
    na = len(dj_av)
    ep_coup = np.matmul(dj_av.T, phonons['vectors'])
    ssigma = (1 / na) * np.sum(ep_coup**2 / \
        (2 * np.tanh(phonons['energies'] / (2 * temp))))

    return np.sqrt(ssigma)

def get_jdelta(pair, delta=0.01, phonons, temp):
    jlists = []
    # run Gaussian for displacements of first molecule
    mol1 = str(pair[1][0] + 1)
    with chdir(mol1):
        mkdir('displacements')
        with chdir('displacements'):
            copyfile('../' + mol1 + '.xyz', 'static.xyz')
            finite_dif(delta / 2)
            finite_dif(delta)

    # run Gaussian for displacements of first molecule in the pair
    molpair = str(pair[0])
    with chdir(molpair):
        mkdir('displacements')
        with chdir('displacements'):
            copyfile('../' + molpair + '.xyz', 'static.xyz')
            finite_dif(delta / 2, all=False)
            finite_dif(delta, all=False)

    # calculating j for each displacement
    path1 = mol1 + '/' + mol1 + 'displacements/'
    path2 = str(pair[1][0] + 1) + '/' + str(pair[1][0] + 1)
    path3 = molpair + '/' + molpair

    atoms = read(path1 + 'static.xyz')
    for d in [delta/2, delta]:
        js = []
        for ia, iv, sign in get_displacements(atoms, all=all):
            prefix = 'dj-{}-{}{}{}' .format(int(d * 1000), 
                                                ia,
                                                'xyz'[iv],
                                                ' +-'[sign])
            j = catnip(path1 + prefix, path2, path3 + prefix)
            js.append(j)
        jlists.append(js)

    # Create GradJ matrix with a atoms and v directions
    dj_matrix_av = get_dj_matrix(jlists, delta)

    # Calculate variance
    sigma = get_fluctuations(dj_matrix_av, phonons, temp)
    print('sigma_{} = {}' .format(pair[0], sigma))

if __name__ == '__main__':
    pairs = {'A':[0, 1], 
             'B':[1, 2],
             'C':[0, 2]}
    
    for pair in pairs.items():
        get_jdelta(pair, delta=0.01)
