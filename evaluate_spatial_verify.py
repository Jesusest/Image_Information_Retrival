from __future__ import print_function
from toolkit.descriptors import DetectAndDescribe
from toolkit.ir import BagOfVisualWords
from toolkit.ir import SpatialVerifier
from toolkit.ir import Searcher
from scipy.spatial import distance
from redis import Redis
from imutils.feature import FeatureDetector_create, DescriptorExtractor_create
import numpy as np
import progressbar
import argparse
import pickle
import imutils
import json
import cv2

# Construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-d", "--dataset", required=True, help="Path to the directory of indexed images")
ap.add_argument("-f", "--features-db", required=True, help="Path to the features database")
ap.add_argument("-b", "--bovw-db", required=True, help="Path to the bag-of-visual-words database")
ap.add_argument("-c", "--codebook", required=True, help="Path to the codebook")
ap.add_argument("-i", "--idf", type=str, help="Path to inverted document frequencies array")
ap.add_argument("-r", "--relevant", required=True, help = "Path to relevant dictionary")
args = vars(ap.parse_args())

# Initialize the keypoints detector, local invariant descriptor, and pipeline
detector = FeatureDetector_create("SURF")
descriptor = DescriptorExtractor_create("RootSIFT")
dad = DetectAndDescribe(detector, descriptor)

# Load the inverted document frequency array and codebook vocabulary, then
# initialize the bag-of-visual-words transformer
idf = pickle.loads(open(args["idf"], "rb").read())
vocab = pickle.loads(open(args["codebook"], "rb").read())
bovw = BagOfVisualWords(vocab)

# Connect to redis and initialize the searcher and spatial verifier
redisDB = Redis(host="localhost", port=6379, db=0)
searcher = Searcher(redisDB, args["bovw_db"], args["features_db"], idf=idf,
	distanceMetric=distance.cosine)
spatialVerifier = SpatialVerifier(args["features_db"], idf, vocab)

# Load the relevant queries dictionary
relevant = json.loads(open(args["relevant"]).read())
queryIDs = relevant.keys()

# Initialize the accuracies list and the timings list
accuracies = []
timings = []

# Initialize the progress bar
widgets = ["Evaluating: ", progressbar.Percentage(), " ", progressbar.Bar(), " ", progressbar.ETA()]
pbar = progressbar.ProgressBar(maxval=len(queryIDs), widgets=widgets).start()

# Loop over the images
for (i, queryID) in enumerate(sorted(queryIDs)):
	# Lookup the relevant results for the query image
	queryRelevant = relevant[queryID]

	# Load the query image and process it
	p = "{}/{}".format(args["dataset"], queryID)
	queryImage = cv2.imread(p)
	queryImage = imutils.resize(queryImage, width=320)
	queryImage = cv2.cvtColor(queryImage, cv2.COLOR_BGR2GRAY)

	# Extract features from the query image and construct a bag-of-visual-words from it
	(kps, descs) = dad.describe(queryImage)
	hist = bovw.describe(descs).tocoo()

	# Perform the search and  then spatially verify
	sr = searcher.search(hist, numResults=20)
	sv = spatialVerifier.rerank(kps, descs, sr, numResults=4)

	# Compute the total number of relevant images in the top-4 results
	results = set([r[1] for r in sv.results[:4]])
	inter = results.intersection(queryRelevant)

	# Update the evaluation lists
	accuracies.append(len(inter))
	timings.append(sr.search_time + sv.search_time)
	pbar.update(i)

# Release any pointers allocated by the searcher
searcher.finish()
pbar.finish()

# Show evaluation information to the user
accuracies = np.array(accuracies)
timings = np.array(timings)
print("[INFO] ACCURACY: u={:.2f}, o={:.2f}".format(accuracies.mean(), accuracies.std()))
print("[INFO] TIMINGS: u={:.2f}, o={:.2f}".format(timings.mean(), timings.std()))