# Import the necessary packages
from .searchresult import SearchResult
from .dists import chi2_distance
import numpy as np
import datetime
import h5py


class Searcher:
    def __init__(self, redisDB, bovwDBPath, featuresDBPath, idf=None,
                 distanceMetric=chi2_distance):
        # Store the redis database reference, the idf array, and the distance metric
        self.redisDB = redisDB
        self.idf = idf
        self.distanceMetric = distanceMetric

        # Open both the bag-of-visual-words database and the features database for reading
        self.bovwDB = h5py.File(bovwDBPath, mode="r")
        self.featuresDB = h5py.File(featuresDBPath, "r")

    def search(self, queryHist, numResults=10, maxCandidates=200):
        # Start the timer to track how long the search took
        startTime = datetime.datetime.now()

        # Determine the candidates and sort them in ascending order so they can
        # be read from the bag-of-visual-words database
        candidateIdxs = self.buildCandidates(queryHist, maxCandidates)
        candidateIdxs.sort()

        # Grab the histograms for the candidates from the bag-of-visual-words
        # database and initialize the results dictionary
        hists = self.bovwDB["bovw"][candidateIdxs]
        queryHist = queryHist.toarray()
        results = {}

        # If the inverse document frequency (idf) array has been supplied, multiply the query by it
        if self.idf is not None:
            queryHist *= self.idf

        # Iterate over the histograms
        for (candidate, hist) in zip(candidateIdxs, hists):
            # If the inverse document frequency array has been supplied, multiply
            # the histogram by it
            if self.idf is not None:
                hist *= self.idf

            # Compute the distance between the histograms and updated the results dictionary
            d = self.distanceMetric(hist, queryHist)
            results[candidate] = d

        # Sort the results, this time replacing the image indexes with the image IDs themselves
        results = sorted([(v, self.featuresDB["image_ids"][k], k)
                          for (k, v) in results.items()])
        results = results[:numResults]

        # Return the search results
        return SearchResult(results, (datetime.datetime.now() - startTime).total_seconds())

    def buildCandidates(self, hist, maxCandidates):
        # Initialize the redis pipeline
        p = self.redisDB.pipeline()

        # Loop over the columns of the (sparse) matrix and create a query to
        # grab all images with an occurrence of the current visual word
        for i in hist.col:
            p.lrange("vw:{}".format(i), 0, -1)

        # Execute the pipeline and initialize the candidates list
        pipelineResults = p.execute()
        candidates = []

        # Loop over the pipeline results, extract the image index, and update
        # the candidates list
        for results in pipelineResults:
            results = [int(r) for r in results]
            candidates.extend(results)

        # Count the occurrence of each of the candidates and sort in descending order
        (imageIdxs, counts) = np.unique(candidates, return_counts=True)
        imageIdxs = [i for (c, i) in sorted(zip(counts, imageIdxs), reverse=True)]

        # Return the image indexes of the candidates
        return imageIdxs[:maxCandidates]

    def finish(self):
        # Close the bag-of-visual-words database and the features database
        self.bovwDB.close()
        self.featuresDB.close()