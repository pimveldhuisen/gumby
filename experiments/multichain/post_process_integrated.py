#!/usr/bin/env python2
"""
Performs database aggregation after an integrated multichain gumby experiment.
"""
import os
import sys

if __name__ == '__main__':
    # Fix the path
    sys.path.append(os.path.abspath('./tribler'))
    sys.path.append(os.path.abspath('./gumby'))
    sys.path.append(os.getcwd())

    working_directory = os.path.abspath("output/")
    if sys.argv == 2:
        working_directory = sys.argv[1]

    # Create an aggregation output directory.
    aggregation_path = os.path.join(working_directory, "sqlite")
    if not os.path.exists(aggregation_path):
        os.makedirs(aggregation_path)

    from DatabaseReader import GumbyIntegratedDatabaseReader

    data = GumbyIntegratedDatabaseReader(working_directory)
    data.database.close()
