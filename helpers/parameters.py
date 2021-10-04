import yaml
import argparse


def load_config(file):
    try:

        with open(file) as file:
            return yaml.load(file, Loader=yaml.FullLoader)
    except FileNotFoundError as fe:
        exit(f'Could not find {file}')
    
    except Exception as e:
        exit(f'Encountered exception...\n {e}')
        
def set_exparis(pairs, file_name):
    parsed_config = load_config(file_name)
    with open(file_name, 'r') as file:
        data = file.readlines()
    EX_PAIRS = parsed_config['trading_options']['EX_PAIRS']
    e = False
    pairs = pairs.strip()
    for coin in EX_PAIRS:
        if coin == pairs: 
            e = True
            break
        else:
            e = False
    if e == False:
        print(f'The exception has been saved in EX_PAIR in the configuration file...')
        EX_PAIRS.append(pairs)
        data[44] = "  EX_PAIRS: " + str(EX_PAIRS) + "\n"
        with open(file_name, 'w') as f:
            f.writelines(data)


def parse_args():
    x = argparse.ArgumentParser()
    x.add_argument('--debug', '-d', help="extra logging", action='store_true')
    x.add_argument('--config', '-c', help="Path to config.yml")
    x.add_argument('--creds', '-u', help="Path to creds file")
    x.add_argument('--notimeout', help="Dont use timeout in prod", action="store_true")
    x.add_argument('--test', '-t', help="Test mode")
    #x.add_argument('--makevlist', '-m', help="Create a Volatile List", action="store_true")
    return x.parse_args()