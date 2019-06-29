import bz2
import json
import os
import textwrap
from io import StringIO
from pandas import DataFrame
import os
import matplotlib.pyplot as plt
import pandas as pd
import pygraphviz as pgv
from tabulate import tabulate

import sys
sys.path.append("..")

from dataset_displayers.tropes_similarity import TropesSimilarityChecker

data = {}

def read_compressed_json(file_path):
    if file_path in data:
        return data[file_path]

    with open(file_path, 'rb') as file:
        compressed_content = file.read()
    content_bytes = bz2.decompress(compressed_content)
    content = json.loads(content_bytes.decode('utf-8'))

    data[file_path] = content
    return content


def reverse_dictionary(original_dictionary):
    reversed_dictionary = {}
    for key, value in original_dictionary.items():
        for element in value:
            if element not in reversed_dictionary:
                reversed_dictionary[element] = []
            reversed_dictionary[element].append(key)
    return reversed_dictionary


def draw_graphviz(dot, filename):
    new_dot = dot.replace('type="start"', 'shape="ellipse" margin=0.2')
    new_dot = new_dot.replace('type="database"', 'shape="cylinder" margin=0.2')
    new_dot = new_dot.replace('type="tool"', 'shape="box" margin=0.2')
    new_dot = new_dot.replace('type="process"', 'shape="box3d" margin=0.2 style="filled" fillcolor="gray91"')
    new_dot = new_dot.replace('type="data"', 'shape="polygon" skew=0.5 margin=0')

    G = pgv.AGraph(string=new_dot)
    G.layout(prog='dot')
    if not os.path.isdir('figures'):
        os.makedirs('figures')
    G.draw(os.path.join('figures', filename))


def get_table_for_dataframe(df, fixed_width=None, **kwargs):
    latex_code = tabulate(df, headers=df, tablefmt='latex_raw', **kwargs)
    latex_code = latex_code.replace('%', '\\%')
    if fixed_width is not None:
        latex_code = latex_code.replace('\\begin{tabular}','\\begin{tabularx}{\\textwidth}')
        latex_code = latex_code.replace('\\end{tabular}', '\\end{tabularx}')
        latex_code = latex_code.replace('{lr}','{Xr}')
        latex_code = latex_code.replace('{rllrrl}', '{rLLrrl}')
        latex_code = latex_code.replace('[GENRE]','')
    return latex_code


def tex_wrap_and_escape(text, length=40):
    if isinstance(text, str):
        wrapped_text = textwrap.fill(text, length)
        if '\n' in wrapped_text:
            wrapped_text = '\makecell[tl]{' + wrapped_text.replace('\n', ' \\\\ ') + '}'
        return tex_escape(wrapped_text)
    if isinstance(text, list):
        text = ', '.join([str(element) for element in text])
        return tex_wrap_and_escape(text)
    return text


def tex_escape(text):
    CHARS = {
        '&': '\&',
        '%': '\%',
        '$': '\$',
        '#': '\#',
        '_': '\_',
        '^': '\^',
    }

    if isinstance(text, str):
        return ("".join([CHARS.get(char, char) for char in text]))

    return text


def get_experiment_execution_information(log_file_path):
    with open(log_file_path, 'r') as scraper_log:
        lines = scraper_log.readlines()
        first_line = lines[0]
        last_line = lines[-1]

    parameters_as_text = first_line.split('Init script: ')[1]
    input_log = json.loads(parameters_as_text)
    keys = [tex_wrap_and_escape(key) for key in input_log.keys()]
    values = [tex_wrap_and_escape(key) for key in input_log.values()]
    processed_dictionary = dict(parameter=keys, value=values)
    input_dataframe = pd.DataFrame.from_dict(processed_dictionary)

    summary_as_text = last_line.split('Finish script: ')[1]
    output_log = json.loads(summary_as_text)
    keys = [tex_wrap_and_escape(key) for key in output_log.keys()]
    values = [tex_wrap_and_escape(key) for key in output_log.values()]
    processed_dictionary = dict(parameter=keys, value=values)
    output_dataframe = pd.DataFrame(processed_dictionary)
    return input_dataframe, output_dataframe


def read_dataframe(file_path, use_hdf=True):
    if file_path in data:
        return data[file_path]

    if file_path.endswith('csv.bz2'):
        content = None

        file_hdf = file_path.replace('csv.bz2', 'h5')
        if os.path.isfile(file_hdf):
            content = pd.read_hdf(file_hdf)
        else:
            with open(file_path, 'rb') as file:
                compressed_content = file.read()
            csv_content = bz2.decompress(compressed_content)
            content = pd.read_csv(StringIO(csv_content.decode('utf-8')))
            if use_hdf:
                content.to_hdf(file_hdf, 'tripdata')

    data[file_path] = content
    return content


def plot_regression(dataframe, x_column, y_column, color='red'):
    Y = dataframe[y_column]
    X = dataframe[x_column]

    X = X.values.reshape(len(X), 1)
    Y = Y.values.reshape(len(Y), 1)

    X_train = X[:-250]
    X_test = X[-250:]
    Y_train = Y[:-250]
    Y_test = Y[-250:]

    from sklearn import linear_model
    regr = linear_model.LinearRegression()

    regr.fit(X_train, Y_train)
    plt.plot(X_test, regr.predict(X_test), color=color, linewidth=3, )


def extract_iterations_from_log(log_file_name):
    iteration_line = '^.*\\| Iteration ([0-9]+), loss = ([0-9\.]+)$'
    validation_score = '^.*\\| Validation score: ([0-9\\-\\+\\.]+)$'

    values = []
    with open(log_file_name, 'r') as scraper_log:
        lines = scraper_log.readlines()
    import re
    for line in lines:
        matches = re.search(iteration_line, line)
        if matches:
            entry = {'iteration': float(matches.group(1)), 'loss': float(matches.group(2))}
            values.append(entry)
        matches = re.search(validation_score, line)
        if matches:
            entry = values[-1]
            entry['validation'] = float(matches.group(1))

    return pd.DataFrame(values)

def extract_grid_parameters_from_log_and_results(log_file_name):
    result_line = '^.*\\| Result: [^\{]*(.*)$'

    values = []
    with open(log_file_name, 'r') as scraper_log:
        lines = scraper_log.readlines()
    import re
    for line in lines:
        matches = re.search(result_line, line)
        if matches:
            text = matches.group(1)
            text = re.sub("'hidden_layer_sizes': \\(([^\\)]*)\\)", "'hidden_layer_sizes': '(\\1)'", text)
            text = text.replace('\'','"')
            entry = json.loads(text)
            entry = {key.replace('_',' '):value for key,value in entry.items()}
            values.append(entry)
    dataframe = pd.DataFrame(values)
    dataframe = dataframe[['activation','alpha','hidden layer sizes','learning rate','max iter','solver','mean','std']]
    dataframe = dataframe.sort_values(by='mean', ascending=False).reset_index(drop=True)
    return dataframe


if __name__=='__main__':
    recommender_log = pd.read_csv('/Users/phd/workspace/made/made_recommender/logs/recommender_summary_copy_od.log',
                                  header=None)
    columns = ['execution', 'solution_length', 'max_evaluations', 'mutation_probability',
               'crossover_probability', 'population_size', 'no_better_results_during_evaluations',
               'seed', 'fitness', 'time'] + [f'trope_{index}' for index in range(0,30)]
    recommender_log.columns = columns

    reduced_dataframe = pd.DataFrame(recommender_log[['execution', 'mutation_probability', 'crossover_probability',
                                                      'population_size', 'fitness','time']])
    group = reduced_dataframe.groupby(['mutation_probability', 'crossover_probability', 'population_size'])
    description_table = group.describe()
    description_table.to_csv('/Users/phd/workspace/made/made_recommender/datasets/ga_best_parameters_summary.csv')
    pass

