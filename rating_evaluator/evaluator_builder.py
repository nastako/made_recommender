from __future__ import print_function

import bz2
import logging
import math
import os
from io import StringIO

import joblib
import pandas as pd
from sklearn.neural_network import MLPRegressor

from common.base_script import BaseScript
from common.log_stdout_through_logger import write_stdout_through_logger


class EvaluatorBuilder(BaseScript):
    EVERYTHING_BUT_TROPES = ['Id', 'NameTvTropes', 'NameIMDB', 'Rating', 'Votes', 'Year']

    def __init__(self, source_extended_dataset, random_seed=0):
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                            datefmt='%m-%d %H:%M:%m', )

        self.source_extended_dataset = source_extended_dataset
        self.random_seed = random_seed

        parameters = dict(source_extended_dataset=source_extended_dataset, random_seed=random_seed)
        BaseScript.__init__(self, parameters)

        self.extended_dataframe = None
        self.trope_names = None
        self.layer_sizes = []
        self.neural_network = None

    def run(self):
        self._load_dataframe()

        self.trope_names = [key for key in self.extended_dataframe.keys() if key not in self.EVERYTHING_BUT_TROPES]
        inputs = self.extended_dataframe.loc[:][self.trope_names].values
        outputs = self.extended_dataframe.loc[:]['Rating'].values
        tropes_count = len(self.trope_names)

        self._calculate_layer_sizes(tropes_count, number_of_layers=3)
        parameters = dict(activation='relu', alpha=0.0001, random_state=self.random_seed,
                          hidden_layer_sizes=tuple(self.layer_sizes[1:-1]),
                          solver='sgd', max_iter=1000, verbose=100, learning_rate='constant',
                          early_stopping=True)
        for key,value in parameters.items():
            self._add_to_summary(key, value)

        self.neural_network = MLPRegressor(**parameters)

        with write_stdout_through_logger(self._logger):
            self.neural_network.fit(inputs, outputs)

    def _calculate_layer_sizes(self, tropes_count, number_of_layers=3):
        # Number of hidden nodes: There is no magic formula for selecting the optimum number of hidden neurons.
        # However, some thumb rules are available for calculating the number of hidden neurons.
        # A rough approximation can be obtained by the geometric pyramid rule proposed by Masters (1993).
        # For a three layer network with n input and m output neurons, the hidden layer would have 𝑛∗𝑚‾‾‾‾‾√ neurons.
        # Ref:
        # 1 Masters, Timothy. Practical neural network recipes in C++. Morgan Kaufmann, 1993.
        # [2] http://www.iitbhu.ac.in/faculty/min/rajesh-rai/NMEICT-Slope/lecture/c14/l1.html

        if number_of_layers == 3:
            self.layer_sizes.append([tropes_count, int(math.sqrt(tropes_count)), 1])
        else:
            self.layer_sizes = [tropes_count, int(math.sqrt(tropes_count * (tropes_count ** (1 / 3)))),
                                int(tropes_count ** (1 / 3)), 1]

        self._add_to_summary('Layer sizes', self.layer_sizes)

    def _load_dataframe(self):
        self.extended_dataframe = None
        hdf_name = self.source_extended_dataset.replace('.csv.bz2', '.h5')
        if os.path.isfile(hdf_name):
            self.extended_dataframe = pd.read_hdf(hdf_name)
        else:
            with open(self.source_extended_dataset, 'rb') as file:
                compressed_content = file.read()
            csv_content = bz2.decompress(compressed_content)
            self.extended_dataframe = pd.read_csv(StringIO(csv_content.decode('utf-8')))

    def pickle(self, target_folder):
        file_name = f'evaluator_{"_".join([str(value) for value in self.layer_sizes])}.sav'
        file_path = os.path.join(target_folder, file_name)

        return_data = {'inputs': self.trope_names, 'evaluator': self.neural_network}
        joblib.dump(return_data, file_path, compress=False)
        self._add_to_summary('Pickled evaluator path', file_path)

    def finish(self):
        self._finish_and_summary()
