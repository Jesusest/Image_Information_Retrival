from .baseindexer import BaseIndexer
import numpy as np
import h5py
import sys


class FeatureIndexer(BaseIndexer):
    def __init__(self, dbPath, estNumImages=500, maxBufferSize=50000, dbResizeFactor=2,
                 verbose=True):
        # Call the parent constructor
        super(FeatureIndexer, self).__init__(dbPath, estNumImages=estNumImages,
                                             maxBufferSize=maxBufferSize, dbResizeFactor=dbResizeFactor,
                                             verbose=verbose)
        # Open the HDF5 database for writing and initialize the datasets within the group
        self.db = h5py.File(self.dbPath, mode="w")
        self.imageIDDB = None
        self.indexDB = None
        self.featuresDB = None

        # Initialize the image IDs buffer, index buffer, and the keypoints + features buffer
        self.imageIDBuffer = []
        self.indexBuffer = []
        self.featuresBuffer = None

        # Initialize the total number of features in the buffer along with the indexes dictionary
        self.totalFeatures = 0
        self.idxs = {"index": 0, "features": 0}

    def add(self, imageID, kps, features):
        # Compute the starting and ending index for the features lookup
        start = self.idxs["features"] + self.totalFeatures
        end = start + len(features)

        # Update the image IDs buffer, features buffer, and index buffer, followed by incrementing the feature count
        self.imageIDBuffer.append(imageID)
        self.featuresBuffer = BaseIndexer.featureStack(np.hstack([kps, features]),
                                                       self.featuresBuffer)
        self.indexBuffer.append((start, end))
        self.totalFeatures += len(features)

        # Check to see if we have reached the maximum buffer size
        if self.totalFeatures >= self.maxBufferSize:
            # If the databases have not been created yet, create them
            if None in (self.imageIDDB, self.indexDB, self.featuresDB):
                self._debug("initial buffer full")
                self._createDatasets()

            # Write the buffers to file
            self._writeBuffers()

    def _createDatasets(self):
        # Compute the average number of features extracted from the initial buffer
        # Use this number to determine the approximate number of features for the entire dataset
        avgFeatures = self.totalFeatures / float(len(self.imageIDBuffer))
        approxFeatures = int(avgFeatures * self.estNumImages)

        # Grab the feature vector size
        fvectorSize = self.featuresBuffer.shape[1]

        # Handle h5py datatype for Python 2.7
        if sys.version_info[0] < 3:
            dt = h5py.special_dtype(vlen=unicode)

        # Otherwise use a datatype compatible with Python 3+
        else:
            dt = h5py.special_dtype(vlen=str)

        # Initialize the datasets
        self._debug("Creating datasets...")
        self.imageIDDB = self.db.create_dataset("image_ids", (self.estNumImages,),
                                                maxshape=(None,), dtype=dt)
        self.indexDB = self.db.create_dataset("index", (self.estNumImages, 2),
                                              maxshape=(None, 2), dtype="int")
        self.featuresDB = self.db.create_dataset("features",
                                                 (approxFeatures, fvectorSize), maxshape=(None, fvectorSize),
                                                 dtype="float")

    def _writeBuffers(self):
        # Write the buffers to disk
        self._writeBuffer(self.imageIDDB, "image_ids", self.imageIDBuffer,
                          "index")
        self._writeBuffer(self.indexDB, "index", self.indexBuffer, "index")
        self._writeBuffer(self.featuresDB, "features", self.featuresBuffer,
                          "features")

        # Increment the indexes
        self.idxs["index"] += len(self.imageIDBuffer)
        self.idxs["features"] += self.totalFeatures

        # Reset the buffers and feature counts
        self.imageIDBuffer = []
        self.indexBuffer = []
        self.featuresBuffer = None
        self.totalFeatures = 0

    def finish(self):
        # If the databases have not been initialized, then the original buffers were never filled up
        if None in (self.imageIDDB, self.indexDB, self.featuresDB):
            self._debug("minimum init buffer not reached", msgType="[WARN]")
            self._createDatasets()

        # Write any unempty buffers to file
        self._debug("writing un-empty buffers...")
        self._writeBuffers()

        # Compact datasets
        self._debug("compacting datasets...")
        self._resizeDataset(self.imageIDDB, "image_ids", finished=self.idxs["index"])
        self._resizeDataset(self.indexDB, "index", finished=self.idxs["index"])
        self._resizeDataset(self.featuresDB, "features", finished=self.idxs["features"])

        # Close the database
        self.db.close()