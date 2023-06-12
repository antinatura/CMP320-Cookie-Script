"""
Name: cookies.py
Desc: cookie value over time visualisation tool
Auth: Ance Strazdina
Date: 22/05/2023
"""

# imports
import argparse, sys, multiprocessing, tldextract, requests, csv, time
from pathlib import Path
from datetime import datetime
from collections import Counter
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# global variables
c_files, cache = [], []

# get cookie names and values and write to csv
def get_cookies(url, payload, reqs, throttle):
    print("Getting cookies...")
    print(f"Using payload: {payload}")
    print(f"Throttling: {throttle}")

    # make an output directory based on the domain name and current time
    domain = tldextract.extract(url).domain
    timestamp = datetime.now().strftime('%d%m%y_%H%M%S')
    path = domain + '_' + timestamp + '/'
    Path(path).mkdir(exist_ok=True)
    print(f"Results will be written to '{path}'")

    timeout = 15 # connection-timeout for requests, to avoid the script hanging

    try:
        for x in range (reqs):
            # make the request and post data (if any)
            sess = requests.Session()
            auth = sess.post(url, data=payload, timeout = timeout)
            resp = sess.get(url, timeout = timeout)
            cookies = sess.cookies.get_dict() # get cookie names and values in a dict

            # iterate thorugh the dictionary if there are multiple cookies
            for key, value in cookies.items():
                filename = path + key + '.csv'

                # keep track of how many different cookie files are created so they can all be parsed later
                if filename not in c_files:
                    c_files.append(filename)

                # make (or open) the csv file and append the cookie and timestamp
                with open(filename, 'a', newline='') as file:
                    writer = csv.writer(file)
                    row = [datetime.now(), value]
                    writer.writerow(row)

            # basic delay
            if throttle:
                time.sleep(0.5)

    except Exception as e:
        Path(path).rmdir() # delete the empty directory
        sys.exit(f"Script terminated due to encountered exceptions: {str(e)}")

# parse the cookie csv file and update it with the encoded values
def parse(filename):
    probabilities = {}

    # open cookie file
    with open(filename, 'r') as file:
        reader = csv.reader(file)
        newdata = []

        # encode each cookie and add the value to the list
        for row in reader:
            newdata.append(encode(row[1], probabilities))
        
        # rewrite the file adding encoded values and labels
        df = pd.read_csv(filename, names=['Time', 'Value'])
        df['Decimal Value'] = newdata
        df.to_csv(filename, index = False)

# main cookie encoding function
def encode(cookie, probabilities):
    # to avoid repeated calculations check if there is a cached cookie and encoded value
    # if list is not empty compare current and previous cookie, if the cookie value is the same use last encoded value and return
    if cache:
        if cookie == cache[0]:
            return cache[1]

    # update character probabilities based on current cookie and encode it using arithmetic encoding
    probabilities = get_probability(cookie, probabilities) 
    encoded_value = arithmetic_encode(cookie, probabilities) 
    
    # add cookie and its encoded value to the cache
    cache.insert(0, cookie)
    cache.insert(1, encoded_value)

    return encoded_value

# get probabilities
def get_probability(cookie, probabilities):
        char_count = Counter(cookie)
        total_chars = len(cookie)
        start = 0.0

        for char, count in char_count.items():
            probability = count / total_chars # occurence of an unique character against the total amount of characters
            end = start + probability # end of distribution

            if char in probabilities:
                # update character probability
                old_start, old_end = probabilities[char]
                new_start = start + old_start * (end - start)
                new_end = start + old_end * (end - start)
                probabilities[char] = (new_start, new_end)
            else:
                probabilities[char] = (start, end) # add previosuly unencountered characters

            start = end # reassign start of next distribution

        return probabilities

# perform arithmetic encoding to encode the cookie value into decimal
def arithmetic_encode(cookie, probabilities):
    # initialize the interval to 0 - 1
    interval_start = 0.0
    interval_size = 1.0
    
    # encode each character in the cookie
    for char in cookie:
        char_range = probabilities[char] # get the probabilities range for the current character
        # update the interval based on the character range
        interval_start += interval_size * char_range[0]
        interval_size *= char_range[1] - char_range[0]

    return (1 - (interval_start + 0.5 * interval_size)) * 10 # return the midpoint of interval as the encoded value. subtracted from 1 for graphing purpouses (encoding makes technically "increasing" cookie values decrease). multiplied by 10 for graphing purpouses

# make a graph
def draw(filename):
    timestamps = []
    values = []

    imagefile = filename[:-4] + '.png' # image file name

    # read the timestamps and encoded cookie values
    with open(filename, 'r') as readf:
        reader = csv.reader(readf, delimiter=',')
        next(reader) # skip the header row

        for row in reader:
            timestamps.append(datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S.%f'))
            values.append(float(row[2]))
    
    plt.scatter(timestamps, values, c = 'r')  # plot the values to a graph
 
    # format the graph
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(7))
    plt.xticks(rotation = 25)
    plt.xlabel('time')
    plt.ylabel('value')
    plt.title(f"{filename[:-4].split('/')[1]} Values Over Time", fontsize = 20)

    plt.savefig(imagefile, bbox_inches='tight') # save the image
    plt.close()

# multiprocessing function
def multiprocess():
    print("Encoding and drawing cookie values...")

    num_processes = multiprocessing.cpu_count()
    pool = multiprocessing.Pool(num_processes)

    pool.map(process, c_files) # process each created cookie CSV file

    pool.close()
    pool.join()

def process(filename):
    parse(filename) # parse the collected data
    draw(filename) # plots the values on graphs and saves them

# main function
def main(args):
    # 1) get url
    url = args.url
   
    # 2) get payload for authentication
    payload = {} # default payload is empty
    
    # if payload is provided, read it into a dictionary
    if args.payload:
        try:
            with open(args.payload) as file:      
                    for line in file:
                        (key, sep, val) = line.strip().partition(',')
                        payload[key] = val
        except OSError:
            sys.exit("No such file or directory!")
        except UnicodeDecodeError:
            sys.exit("Invalid filetype!")

    # 3) get number of requests to make
    reqs = 50 # default number of requests the script will make

    # if request number is provided, use that
    if args.requests:
        reqs = args.requests
        if reqs < 10 or reqs > 200:
            # number is not within the allowed range
            print("Number of requests must be in the range [10, 200], defaulting to 50.")
            reqs = 50

    # 4) get throttle
    throttle = args.throttle

    get_cookies(url, payload, reqs, throttle) # get cookies
    multiprocess() # parse the created cookie files

    print("Done!")

# parse the arguments & call the main function
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog = 'cookies.py',  description = 'Cookie value over time visualisation tool', epilog = 'Ance Strazdina, CMP320 Scripting Project, 2023', add_help = True, formatter_class = argparse.RawTextHelpFormatter)

    parser.add_argument('url', type = str, help = 'url to test. if authenticating, provide the url of the form to post data to.')
    parser.add_argument('-p', '--payload', type = str, help = 'credentials to use for authenticating in a file form. has to follow a comma seperated value\nformat of [fieldname],[value] (including the submit button value) with a new row for each field.\nExample:\n \nusername,user\npassword,pass\nsubmit, \n \n')
    parser.add_argument('-r', '--requests', type = int, help = 'number of requests in the range [10, 200] to make. defaults to 50.')
    parser.add_argument('-t', '--throttle', action='store_true', help = 'use a simple request delay of 0.5 seconds. useful to slow requests down to observe changes if\noutputted graph is a horizontal line.')

    args = parser.parse_args()
    main(args)
