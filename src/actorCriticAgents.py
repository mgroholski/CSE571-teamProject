from game import Directions, Agent, Actions
from pacman import GameState
import random,util,time,math
import sys
from featureExtractors import *

# The Actor-Critic Agent class
class ActorCriticAgent(Agent):
    def __init__(self, actionFn=None, gamma=0.8, alpha_theta=0.2, alpha_w=0.2, numTraining=100):
        if actionFn == None:
            actionFn = lambda state: state.getLegalActions()
        self.actionFn = actionFn

        self.theta = [0,0,0,0]
        self.w = [0,0,0,0]
        self.i = 1

        self.alpha_theta = float(alpha_theta)
        self.alpha_w = float(alpha_w)

        self.gamma = float(gamma)

        self.numTraining = int(numTraining)
        self.episodesSoFar = 0
        self.accumTrainRewards = 0
        self.accumTestRewards = 0

    def getFeatureVector(self, state, action):
        # Features inpsired by https://cs229.stanford.edu/proj2017/final-reports/5241109.pdf
        # extract the grid of food and wall locations and get the ghost locations
        divideAll = 1
        food = state.getFood()
        capsules = state.getCapsules()
        for capsule in capsules:
            food[capsule[0]][capsule[1]] = True

        walls = state.getWalls()
        ghosts = state.getGhostPositions()
        activeGhostsPositions = []
        for g in state.getGhostStates():
            if g.scaredTimer <= 3:
                activeGhostsPositions.append(g.getPosition())

        # compute the location of pacman after he takes the action
        x, y = state.getPacmanPosition()
        dx, dy = Actions.directionToVector(action)
        next_x, next_y = int(x + dx), int(y + dy)

        nDistanceGhosts = sum((next_x, next_y) in Actions.getLegalNeighbors(g, walls) for g in activeGhostsPositions)

        eatFood = 0
        if nDistanceGhosts == 0:
            eatFood = 1

        dist = closestFood((next_x, next_y), food, walls)
        if dist is not None:
            closestFoodDist = float(dist)
        else:
            closestFoodDist = sys.maxsize

        numScaredGhost = sum(g.scaredTimer > 0 for g in state.getGhostStates())

        return [closestFoodDist / divideAll,
            nDistanceGhosts / divideAll,
            eatFood / divideAll,
            numScaredGhost /divideAll
        ]

    def softmaxPolicy(self, state, action):
        # Implementation Help: https://towardsdatascience.com/policy-based-reinforcement-learning-the-easy-way-8de9a3356083
        numeratorFeatureVector = self.getFeatureVector(state, action)

        if len(numeratorFeatureVector) != len(self.theta):
            print(f"Theta (Legnth {len(self.theta)}) and Feature Vector (Length {len(numeratorFeatureVector)}) are different lengths.")
            exit()

        hValue = 0
        for i in range(len(self.theta)):
            hValue += self.theta[i] * numeratorFeatureVector[i]

        try:
            numerator = math.exp(hValue)
        except:
            if hValue < 0:
                numerator = 0
            else:
                numerator = sys.maxsize

        denominator = 0
        for legalAction in self.getLegalActions(state):
            featureVector = self.getFeatureVector(state, legalAction)
            hValue = 0
            for i in range(len(self.theta)):
                hValue += self.theta[i] * featureVector[i]

            try:
                denominator += math.exp(hValue)
            except:
                if hValue < 0:
                    denominator += 0
                else:
                    denominator += sys.maxsize

        # if numerator == 0:
        #     print("Numerator is zero: \n\tFeature Vec:", numeratorFeatureVector, "\n\tDenominator: ", denominator,"\n\t Theta: ", thetaVector)

        if denominator == 0:
            for legalAction in self.getLegalActions(state):
                featureVector = self.getFeatureVector(state, legalAction)
                print("Denominator is Zero!\n\tAction:", legalAction, "\n\tFeature Vector:", featureVector)
        return (numerator / denominator) if denominator != 0 else 0

    def getAction(self, state):
        actionProbabilities = []
        probabilitySum = 0
        for action in self.getLegalActions(state):
            probability = self.softmaxPolicy(state, action)
            actionProbabilities.append((probability, action))
            probabilitySum += probability

        randomNum = random.random()
        for action in actionProbabilities:
            randomNum -= action[0]
            if randomNum <= 0:
                self.doAction(state, action[1])
                return action[1]

        print("Did not find a legal action!")
        print("Action Probabilities: ", actionProbabilities)

        #Choose action uniformly at random
        return random.choice(self.getLegalActions(state))

    def expectedFeatures(self, state):
        expectedFeatures = [0.0] * len(self.theta)
        for legalAction in self.getLegalActions(state):
            featureValue = self.getFeatureVector(state, legalAction)
            actionProbability = self.softmaxPolicy(state, legalAction)
            for i in range(len(expectedFeatures)):
                expectedFeatures[i] += actionProbability * featureValue[i]
        return expectedFeatures


    def getValue(self, state):
        expectedFeaturesVector = self.expectedFeatures(state)
        value = 0
        for i in range(len(expectedFeaturesVector)):
            value += self.w[i] * expectedFeaturesVector[i]

        return value

    def getLegalActions(self,state):
        """s
          Get the actions available for a given
          state. This is what you should use to
          obtain legal actions for a state
        """
        return self.actionFn(state)

    def observeTransition(self, state, action, nextState, deltaReward):
        """
            Called by environment to inform agent that a transition has
            been observed. This will result in a call to self.update
            on the same arguments

            NOTE: Do *not* override or call this function
        """
        self.episodeRewards += deltaReward

        delta = deltaReward
        if not (nextState.isWin() or nextState.isLose()):
            delta += self.gamma * self.getValue(nextState) - self.getValue(state)

        valueVector = self.expectedFeatures(state)
        for i in range(len(self.w)):
            self.w[i] += self.alpha_w * self.i * delta * valueVector[i]

        # Calculates gradient vector
        featureVector = self.getFeatureVector(state, action)

        gradientVector = [0.0] * len(self.theta)
        actionProbabilties = []
        actionFeatureVectors = []

        for legalAction in self.getLegalActions(state):
            actionProbabilties.append(self.softmaxPolicy(state, legalAction))
            actionFeatureVectors.append(self.getFeatureVector(state, legalAction))

        # x(s,a) - Sum pi(s,*)x(s,*)
        for i in range(len(gradientVector)):
            actionSum = 0
            for j in range(len(actionProbabilties)):
                actionSum += actionProbabilties[j] * actionFeatureVectors[j][i]
            gradientVector[i] = featureVector[i] - actionSum

        for j in range(len(self.theta)):
            self.theta[j] += self.alpha_theta * self.i * delta * gradientVector[j]

        self.i *= self.gamma


    def startEpisode(self):
        """
          Called by environment when new episode is starting
        """
        self.episodeRewards = 0.0
        self.i = 1

        self.lastState = None
        self.lastAction = None

    def stopEpisode(self):
        """
          Called by environment when episode is done
        """
        # print(self.w)
        # print(self.theta)
        print(f"Episode {self.episodesSoFar} finished")

        if self.episodesSoFar < self.numTraining:
            self.accumTrainRewards += self.episodeRewards
        else:
            self.accumTestRewards += self.episodeRewards
        self.episodesSoFar += 1
        if self.episodesSoFar >= self.numTraining:
            # Take off the training wheels
            self.epsilon = 0.0    # no exploration
            self.alpha = 0.0      # no learning

    def isInTraining(self):
        print("In training")
        return self.episodesSoFar < self.numTraining

    def isInTesting(self):
        print("In Test phase")
        return not self.isInTraining()

    ################################
    # Controls needed for Crawler  #
    ################################
    def setEpsilon(self, epsilon):
        self.epsilon = 0

    def setLearningRate(self, alpha):
        self.alpha = 0

    def setDiscount(self, discount):
        self.discount = 0

    def doAction(self,state,action):
        """
            Called by inherited class when
            an action is taken in a state
        """
        self.lastState = state
        self.lastAction = action

    ###################
    # Pacman Specific #
    ###################
    def observationFunction(self, state):
        """
            This is where we ended up after our last action.
            The simulation should somehow ensure this is called
        """
        if not self.lastState is None:
            reward = state.getScore() - self.lastState.getScore()
            self.observeTransition(self.lastState, self.lastAction, state, reward)
        return state

    def registerInitialState(self, state):
        self.startEpisode()
        if self.episodesSoFar == 0:
            print('Beginning %d episodes of Training' % (self.numTraining))

    def final(self, state):
        """
          Called by Pacman game at the terminal state
        """
        deltaReward = state.getScore() - self.lastState.getScore()
        self.observeTransition(self.lastState, self.lastAction, state, deltaReward)
        self.stopEpisode()

        # Make sure we have this var
        if not 'episodeStartTime' in self.__dict__:
            self.episodeStartTime = time.time()
        if not 'lastWindowAccumRewards' in self.__dict__:
            self.lastWindowAccumRewards = 0.0
        self.lastWindowAccumRewards += state.getScore()


        NUM_EPS_UPDATE = 100
        if self.episodesSoFar % NUM_EPS_UPDATE == 0:
            print('Actor Critic Learning Status:')
            windowAvg = self.lastWindowAccumRewards / float(NUM_EPS_UPDATE)
            if self.episodesSoFar <= self.numTraining:
                trainAvg = self.accumTrainRewards / float(self.episodesSoFar)
                print('\tCompleted %d out of %d training episodes' % (
                       self.episodesSoFar,self.numTraining))
                print('\tAverage Rewards over all training: %.2f' % (
                        trainAvg))
            else:
                testAvg = float(self.accumTestRewards) / (self.episodesSoFar - self.numTraining)
                print('\tCompleted %d test episodes' % (self.episodesSoFar - self.numTraining))
                print('\tAverage Rewards over testing: %.2f' % testAvg)
            print('\tAverage Rewards for last %d episodes: %.2f'  % (
                    NUM_EPS_UPDATE,windowAvg))
            print('\tEpisode took %.2f seconds' % (time.time() - self.episodeStartTime))
            self.lastWindowAccumRewards = 0.0
            self.episodeStartTime = time.time()

        if self.episodesSoFar == self.numTraining:
            msg = 'Training Done (turning off epsilon and alpha)'
            print('%s\n%s' % (msg,'-' * len(msg)))
