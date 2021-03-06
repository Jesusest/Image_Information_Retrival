from sklearn.metrics import pairwise
from scipy.sparse import csr_matrix
import numpy as np


class BagOfVisualWords:
    def __init__(self, codebook, sparse=True):
        # Store the codebook used to compute the bag-of-visual-words representation for each
        # image along with the flag used to control whether sparse or dense histograms are constructed
        self.codebook = codebook
        self.sparse = sparse

    def describe(self, features):
        # Compute the Euclidean distance between the features and cluster centers,
        # grab the indexes of the smallest distances for each cluster, and construct
        # a bag-of-visual-words representation
        D = pairwise.euclidean_distances(features, Y=self.codebook)
        (words, counts) = np.unique(np.argmin(D, axis=1), return_counts=True)

        # Check to see if a sparse histogram should be constructed
        if self.sparse:
            hist = csr_matrix((counts, (np.zeros((len(words),)), words)),
                              shape=(1, len(self.codebook)), dtype="float")

        # Otherwise, construct a dense histogram of visual word counts
        else:
            hist = np.zeros((len(self.codebook),), dtype="float")
            hist[words] = counts

        # Return the histogram of visual word counts
        return hist