from toontown.suit import DistributedFactorySuitAI
from direct.directnotify import DirectNotifyGlobal

class DistributedStageSuitAI(DistributedFactorySuitAI.DistributedFactorySuitAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedStageSuitAI')

    def isClerk(self):
        return self.boss

    def isVirtual(self):
        return self.virtual
