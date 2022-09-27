from libotp import *
from direct.interval.IntervalGlobal import *
from direct.distributed.ClockDelta import *
from direct.showbase.PythonUtil import Functor
from direct.gui.DirectGui import *
from direct.fsm import FSM
from direct.fsm import ClassicFSM
from direct.fsm import State
from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import ToontownBattleGlobals
import DistributedBossCog
from toontown.toonbase import TTLocalizer
import SuitDNA
from toontown.toon import Toon
from toontown.battle import BattleBase
from direct.directutil import Mopath
from direct.showutil import Rope
from toontown.distributed import DelayDelete
from toontown.battle.movies import MovieToonVictory, RewardPanel
from direct.task import Task
import random
import math
from toontown.coghq import CogDisguiseGlobals, BossHealthBar
from toontown.suit.SellbotBossGlobals import *

OneBossCog = None


class DistributedSellbotBoss(DistributedBossCog.DistributedBossCog, FSM.FSM):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedSellbotBoss')
    cageHeights = [100, 81, 63, 44, 25, 18]

    def __init__(self, cr):
        DistributedBossCog.DistributedBossCog.__init__(self, cr)
        FSM.FSM.__init__(self, 'DistributedSellbotBoss')
        self.doobers = []
        self.dooberRequest = None
        self.bossDamage = 0
        self.attackCode = None
        self.attackAvId = 0
        self.recoverRate = 0
        self.recoverStartTime = 0
        self.bossDamageMovie = None
        self.cagedToon = None
        self.cageShadow = None
        self.cageIndex = 0
        self.rescueToon = None
        self.everThrownPie = 0
        self.battleThreeMusicTime = 0
        self.insidesANodePath = None
        self.insidesBNodePath = None
        self.rampA = None
        self.rampB = None
        self.rampC = None
        self.strafeInterval = None
        self.onscreenMessage = None
        self.toonMotionPathInterval = []
        self.nerfed = ToontownGlobals.SELLBOT_NERF_HOLIDAY in base.cr.newsManager.getHolidayIdList()
        self.localToonPromoted = True
        return

    def announceGenerate(self):
        global OneBossCog
        DistributedBossCog.DistributedBossCog.announceGenerate(self)
        self.setName(TTLocalizer.SellbotBossName)
        self.bossHealthBar = BossHealthBar.BossHealthBar(self.style.dept)
        nameInfo = TTLocalizer.BossCogNameWithDept % {'name': self._name,
                                                      'dept': SuitDNA.getDeptFullname(self.style.dept)}
        self.setDisplayName(nameInfo)
        self.cageDoorSfx = loader.loadSfx('phase_5/audio/sfx/CHQ_SOS_cage_door.ogg')
        self.cageLandSfx = loader.loadSfx('phase_9/audio/sfx/CHQ_SOS_cage_land.ogg')
        self.cageLowerSfx = loader.loadSfx('phase_5/audio/sfx/CHQ_SOS_cage_lower.ogg')
        self.piesRestockSfx = loader.loadSfx('phase_9/audio/sfx/CHQ_SOS_pies_restock.ogg')
        self.rampSlideSfx = loader.loadSfx('phase_9/audio/sfx/CHQ_VP_ramp_slide.ogg')
        self.strafeSfx = []
        for i in xrange(10):
            self.strafeSfx.append(loader.loadSfx('phase_3.5/audio/sfx/SA_shred.ogg'))

        render.setTag('pieCode', str(ToontownGlobals.PieCodeNotBossCog))
        insidesA = CollisionPolygon(Point3(4.0, -2.0, 5.0), Point3(-4.0, -2.0, 5.0),
                                    Point3(-4.0, -2.0, 0.5), Point3(4.0, -2.0, 0.5))
        insidesANode = CollisionNode('BossZap')
        insidesANode.addSolid(insidesA)
        insidesANode.setCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.WallBitmask)
        self.insidesANodePath = self.axle.attachNewNode(insidesANode)
        self.insidesANodePath.setTag('pieCode', str(ToontownGlobals.PieCodeBossInsides))
        self.insidesANodePath.stash()
        insidesB = CollisionPolygon(Point3(-4.0, 2.0, 5.0), Point3(4.0, 2.0, 5.0),
                                    Point3(4.0, 2.0, 0.5), Point3(-4.0, 2.0, 0.5))
        insidesBNode = CollisionNode('BossZap')
        insidesBNode.addSolid(insidesB)
        insidesBNode.setCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.WallBitmask)
        self.insidesBNodePath = self.axle.attachNewNode(insidesBNode)
        self.insidesBNodePath.setTag('pieCode', str(ToontownGlobals.PieCodeBossInsides))
        self.insidesBNodePath.stash()
        target = CollisionTube(0, -1, 4, 0, -1, 9, 3.5)
        targetNode = CollisionNode('BossZap')
        targetNode.addSolid(target)
        targetNode.setCollideMask(ToontownGlobals.PieBitmask)
        self.targetNodePath = self.pelvis.attachNewNode(targetNode)
        self.targetNodePath.setTag('pieCode', str(ToontownGlobals.PieCodeBossCog))
        shield = CollisionTube(0, 1, 4, 0, 1, 7, 3.5)
        shieldNode = CollisionNode('BossZap')
        shieldNode.addSolid(shield)
        shieldNode.setCollideMask(ToontownGlobals.PieBitmask | ToontownGlobals.CameraBitmask)
        shieldNodePath = self.pelvis.attachNewNode(shieldNode)
        disk = loader.loadModel('phase_9/models/char/bossCog-gearCollide')
        disk.find('**/+CollisionNode').setName('BossZap')
        disk.reparentTo(self.pelvis)
        disk.setZ(0.8)
        self.loadEnvironment()
        self.__makeCagedToon()
        self.__makeRescueToon()
        self.__loadMopaths()
        if OneBossCog:
            self.notify.warning('Multiple BossCogs visible.')
        OneBossCog = self
        return

    def disable(self):
        global OneBossCog
        DistributedBossCog.DistributedBossCog.disable(self)
        self.request('Off')
        self.unloadEnvironment()
        self.__unloadMotionPaths()
        self.__cleanupCagedToon()
        self.__cleanupRescueToon()
        self.__clearOnscreenMessage()
        taskMgr.remove(self.uniqueName('PieAdvice'))
        self.__cleanupStrafe()
        render.clearTag('pieCode')
        self.targetNodePath.detachNode()
        self.cr.relatedObjectMgr.abortRequest(self.dooberRequest)
        self.dooberRequest = None
        self.betweenBattleMusic.stop()
        self.introMusic.stop()
        self.stingMusic.stop()
        self.battleTwoMusic.stop()
        self.battleThreeMusic.stop()
        self.epilogueMusic.stop()
        self.bossHealthBar.cleanup()
        while len(self.toonMotionPathInterval):
            toonMotionPath = self.toonMotionPathInterval[0]
            toonMotionPath.finish()
            toonMotionPath.destroy()
            self.toonMotionPathInterval.remove(toonMotionPath)

        if OneBossCog == self:
            OneBossCog = None
        return

    def resetMaxDamage(self):
        if self.nerfed:
            self.bossMaxDamage = SellbotBossMaxDamageNerfed
        else:
            self.bossMaxDamage = SellbotBossMaxDamage[self.battleTier]

    def b_hitBoss(self, bossDamage, toon):
        self.hitBoss(bossDamage)
        if toon == localAvatar:
            self.d_hitBoss(bossDamage)
            self.bossHealthBar.updateDamageDealt(toon.doId, bossDamage)

    def d_hitBoss(self, bossDamage):
        self.sendUpdate('hitBoss', [bossDamage])

    def hitBoss(self, bossDamage):
        self.flashRed()
        self.doAnimate('hit', now=1)
        self.showHpText(-bossDamage, scale=3.5)

    def hitBossBonus(self, bossDamage):
        self.showHpText(-bossDamage, scale=3.5, bonus=1)

    def d_hitBossInsides(self):
        self.sendUpdate('hitBossInsides', [])

    def d_hitToon(self, toonId):
        self.sendUpdate('hitToon', [toonId])

    def setCagedToonNpcId(self, npcId):
        pass

    def gotToon(self, toon):
        stateName = self.state
        if stateName == 'Elevator':
            self.placeToonInElevator(toon)

    def setDooberIds(self, dooberIds):
        self.doobers = []
        self.cr.relatedObjectMgr.abortRequest(self.dooberRequest)
        self.dooberRequest = self.cr.relatedObjectMgr.requestObjects(dooberIds, allCallback=self.__gotDoobers)

    def __gotDoobers(self, doobers):
        self.dooberRequest = None
        self.doobers = doobers
        return

    def setBossDamage(self, bossDamage, recoverRate, timestamp):
        if hasattr(self, 'bossMaxDamage'):
            self.bossHealthBar.update(self.bossMaxDamage - bossDamage, self.bossMaxDamage)
        recoverStartTime = globalClockDelta.networkToLocalTime(timestamp)
        self.bossDamage = bossDamage
        self.recoverRate = recoverRate
        self.recoverStartTime = recoverStartTime
        taskName = 'RecoverBossDamage'
        taskMgr.remove(taskName)
        if self.bossDamageMovie:
            if self.bossDamage >= self.bossMaxDamage:
                self.bossDamageMovie.resumeUntil(self.bossDamageMovie.getDuration())
            else:
                self.bossDamageMovie.resumeUntil(self.bossDamage * self.bossDamageToMovie)
                if self.recoverRate:
                    taskMgr.add(self.__recoverBossDamage, taskName)

    def getBossDamage(self):
        now = globalClock.getFrameTime()
        elapsed = now - self.recoverStartTime
        return max(self.bossDamage - self.recoverRate * elapsed / 60.0, 0)

    def addBonusDamage(self, bonusDamage):
        self.bossDamage += bonusDamage
        if hasattr(self, 'bossMaxDamage'):
            self.bossHealthBar.update(self.bossMaxDamage - self.bossDamage, self.bossMaxDamage)
        taskName = 'RecoverBossDamage'
        taskMgr.remove(taskName)
        if self.bossDamageMovie:
            if self.bossDamage >= self.bossMaxDamage:
                self.bossDamageMovie.resumeUntil(self.bossDamageMovie.getDuration())
            else:
                self.bossDamageMovie.resumeUntil(self.bossDamage * self.bossDamageToMovie)
                if self.recoverRate:
                    taskMgr.add(self.__recoverBossDamage, taskName)

    def __recoverBossDamage(self, task):
        self.bossDamageMovie.setT(self.getBossDamage() * self.bossDamageToMovie)
        return Task.cont

    def __makeCagedToon(self):
        if self.cagedToon:
            return
        dnaNetString = 't\x06\x01\x00\x00\x6f\x1b\x62\x1b\x2d\x1b\x17\x00\x17\x17'
        npc = Toon.Toon()
        npc.setName(TTLocalizer.CagedToonName)
        npc.setDNAString(dnaNetString)
        npc.setPickable(0)
        npc.setPlayerType(NametagGroup.CCNonPlayer)
        self.cagedToon = npc
        self.cagedToon.addActive()
        self.cagedToon.reparentTo(self.cage1)
        self.cagedToon.setPosHpr(1, -2, 0, 180, 0, 0)
        self.cagedToon.loop('neutral')

    def __makeRescueToon(self):
        if self.rescueToon:
            return
        dnaNetString = 't\x1a\x01\x02\x01\x6f\x1b\x62\x1b\x29\x1b\x02\x00\x02\x02'
        npc = Toon.Toon()
        npc.setName(TTLocalizer.RescueToonName)
        npc.setDNAString(dnaNetString)
        npc.setPickable(0)
        npc.setPlayerType(NametagGroup.CCNonPlayer)
        self.rescueToon = npc
        self.rescueToon.addActive()
        self.rescueToon.loop('neutral')
        self.rescueToon.reparentTo(self.cage1)
        self.rescueToon.setPosHpr(-1, -2, 0, 180, 0, 0)

    def __makeCooler(self):
        touch = CollisionPolygon(Point3(-3.0382, 3.0382, -1), Point3(3.0382, 3.0382, -1), Point3(3.0382, -3.0382, -1),
                                 Point3(-3.0382, -3.0382, -1))
        touchNode = CollisionNode('Cage')
        touchNode.setCollideMask(ToontownGlobals.WallBitmask)
        touchNode.addSolid(touch)
        self.cage1.attachNewNode(touchNode)

    def __cleanupCagedToon(self):
        if self.cagedToon:
            self.cagedToon.removeActive()
            self.cagedToon.delete()
            self.cagedToon = None
        return

    def __cleanupRescueToon(self):
        if self.rescueToon:
            self.rescueToon.removeActive()
            self.rescueToon.delete()
            self.rescueToon = None
        return

    def __walkToonToPromotion(self, toonId, delay, mopath, track, delayDeletes):
        toon = base.cr.doId2do.get(toonId)
        if toon:
            destPos = toon.getPos()
            self.placeToonInElevator(toon)
            toon.wrtReparentTo(render)
            walkMopath = MopathInterval(mopath, toon)
            interval = Sequence(Wait(delay), Func(toon.suit.setPlayRate, 1, 'walk'), Func(toon.suit.loop, 'walk'),
                                toon.posInterval(1, Point3(0, 90, 20)),
                                ParallelEndTogether(walkMopath, toon.posInterval(2, destPos, blendType='noBlend')),
                                Func(toon.suit.loop, 'neutral'))
            self.toonMotionPathInterval.append(walkMopath)
            track.append(interval)
            delayDeletes.append(DelayDelete.DelayDelete(toon, 'SellbotBoss.__walkToonToPromotion'))

    def __walkDoober(self, suit, delay, turnPos, track, delayDeletes):
        turnPos = Point3(*turnPos)
        turnPosDown = Point3(*SellbotBossDooberTurnPosDown)
        flyPos = Point3(*SellbotBossDooberFlyPos)
        seq = Sequence(Func(suit.headsUp, turnPos), Wait(delay), Func(suit.loop, 'walk', 0),
                       self.__walkSuitToPoint(suit, suit.getPos(), turnPos),
                       self.__walkSuitToPoint(suit, turnPos, turnPosDown),
                       self.__walkSuitToPoint(suit, turnPosDown, flyPos), suit.beginSupaFlyMove(flyPos, 0, 'flyAway'),
                       Func(suit.fsm.request, 'Off'))
        track.append(seq)
        delayDeletes.append(DelayDelete.DelayDelete(suit, 'SellbotBoss.__walkDoober'))

    def __walkSuitToPoint(self, node, fromPos, toPos):
        vector = Vec3(toPos - fromPos)
        distance = vector.length()
        time = distance / (ToontownGlobals.SuitWalkSpeed * 1.8)
        return Sequence(Func(node.setPos, fromPos), Func(node.headsUp, toPos), node.posInterval(time, toPos))

    def makeIntroductionMovie(self, delayDeletes):
        track = Parallel()
        camera.reparentTo(render)
        camera.setPosHpr(0, 25, 30, 0, 0, 0)
        localAvatar.setCameraFov(ToontownGlobals.CogHQCameraFov)
        dooberTrack = Parallel()
        if self.doobers:
            self.__doobersToPromotionPosition(self.doobers[:4], self.battleANode)
            self.__doobersToPromotionPosition(self.doobers[4:], self.battleBNode)
            turnPosA = SellbotBossDooberTurnPosA
            turnPosB = SellbotBossDooberTurnPosB
            self.__walkDoober(self.doobers[0], 0, turnPosA, dooberTrack, delayDeletes)
            self.__walkDoober(self.doobers[1], 4, turnPosA, dooberTrack, delayDeletes)
            self.__walkDoober(self.doobers[2], 8, turnPosA, dooberTrack, delayDeletes)
            self.__walkDoober(self.doobers[3], 12, turnPosA, dooberTrack, delayDeletes)
            self.__walkDoober(self.doobers[7], 2, turnPosB, dooberTrack, delayDeletes)
            self.__walkDoober(self.doobers[6], 6, turnPosB, dooberTrack, delayDeletes)
            self.__walkDoober(self.doobers[5], 10, turnPosB, dooberTrack, delayDeletes)
            self.__walkDoober(self.doobers[4], 14, turnPosB, dooberTrack, delayDeletes)
        toonTrack = Parallel()
        self.__toonsToPromotionPosition(self.toonsA, self.battleANode)
        self.__toonsToPromotionPosition(self.toonsB, self.battleBNode)
        delay = 0
        for toonId in self.toonsA:
            self.__walkToonToPromotion(toonId, delay, self.toonsEnterA, toonTrack, delayDeletes)
            delay += 1

        for toonId in self.toonsB:
            self.__walkToonToPromotion(toonId, delay, self.toonsEnterB, toonTrack, delayDeletes)
            delay += 1

        toonTrack.append(Sequence(Wait(delay), self.closeDoors))
        self.rampA.request('extended')
        self.rampB.request('extended')
        self.rampC.request('retracted')
        self.clearChat()
        self.cagedToon.clearChat()
        self.rescueToon.clearChat()
        promoteDoobers = TTLocalizer.SellbotBossReports
        doobersAway = TTLocalizer.SellbotBossCaptive
        welcomeToons = TTLocalizer.SellbotBossVisitors1
        promoteToons = TTLocalizer.SellbotBossVisitors2
        discoverToons = TTLocalizer.SellbotBossDiscoverToons2
        attackToons = TTLocalizer.SellbotBossAttack
        interruptBoss = TTLocalizer.CagedToonQuestion
        rescueQuery = TTLocalizer.RescueToonFriends
        bossAnimTrack = Sequence(
            ActorInterval(self, 'Ff_speech', startTime=2, duration=10, loop=1),
            ActorInterval(self, 'ltTurn2Wave', duration=2),
            ActorInterval(self, 'wave', duration=4, loop=1),
            ActorInterval(self, 'ltTurn2Wave', startTime=2, endTime=0),
            ActorInterval(self, 'Ff_speech', duration=7, loop=1))
        track.append(bossAnimTrack)
        dialogTrack = Track(
            (0, Parallel(
                camera.posHprInterval(8, Point3(-22, -100, 35), Point3(-10, -13, 0), blendType='easeInOut'),
                IndirectInterval(toonTrack, 0, 18))),
            (5.6, Func(self.setChatAbsolute, promoteDoobers, CFSpeech)),
            (9, IndirectInterval(dooberTrack, 0, 9)),
            (10, Sequence(
                Func(self.clearChat),
                Func(camera.setPosHpr, -23.1, 15.7, 17.2, -160, -2.4, 0))),
            (12, Func(self.setChatAbsolute, doobersAway, CFSpeech)),
            (16, Parallel(
                Func(self.clearChat),
                Func(camera.setPosHpr, -25, -99, 10, -14, 10, 0),
                IndirectInterval(dooberTrack, 14),
                IndirectInterval(toonTrack, 30))),
            (18, Func(self.setChatAbsolute, welcomeToons, CFSpeech)),
            (22, Func(self.setChatAbsolute, promoteToons, CFSpeech)),
            (22.2, Sequence(
                Func(self.cagedToon.nametag3d.setScale, 2),
                Func(self.rescueToon.nametag3d.setScale, 2),
                Func(self.cagedToon.setChatAbsolute, interruptBoss, CFSpeech),
                ActorInterval(self.cagedToon, 'wave'),
                Func(self.cagedToon.loop, 'neutral'))),
            (25, Sequence(
                Func(self.clearChat),
                Func(self.cagedToon.clearChat),
                Func(camera.setPosHpr, -12, -15, 27, -151, -15, 0),
                ActorInterval(self, 'Ff_lookRt'))),
            (27, Sequence(
                Func(self.rescueToon.setChatAbsolute, rescueQuery, CFSpeech),
                Func(camera.setPosHpr, -12, 48, 94, -26, 20, 0),
                ActorInterval(self.cagedToon, 'wave'),
                Func(self.cagedToon.loop, 'neutral'))),
            (31, Parallel(Func(base.playMusic, self.revealMusic, looping=0, volume=1),
                          Sequence(Func(camera.setPosHpr, -20, -35, 10, -88, 25, 0),
                                   Func(self.setChatAbsolute, discoverToons, CFSpeech),
                                   Func(self.cagedToon.nametag3d.setScale, 1),
                                   Func(self.rescueToon.nametag3d.setScale, 1),
                                   Func(self.rescueToon.clearChat),
                                   Parallel(ActorInterval(self, 'turn2Fb'),
                                            Sequence(Wait(0.6),
                                                     SoundInterval(self.headShakeSfx, volume=0.6, node=self)))))),
            (34, Sequence(Func(self.clearChat),
                          self.loseCogSuits(self.toonsA, self.battleANode, (0, 18, 5, -180, 0, 0)),
                          self.loseCogSuits(self.toonsB, self.battleBNode, (0, 18, 5, -180, 0, 0)))),
            (37, Parallel(Func(base.playMusic, self.introMusic, looping=0, volume=1),
                          Sequence(self.toonNormalEyes(self.involvedToons),
                                   Func(camera.setPosHpr, -23.4, -145.6, 44.0, -10.0, -12.5, 0),
                                   Func(self.loop, 'Fb_neutral'),
                                   Func(self.rampA.request, 'retract'),
                                   Func(self.rampB.request, 'retract'),
                                   Parallel(self.backupToonsToBattlePosition(self.toonsA, self.battleANode),
                                            self.backupToonsToBattlePosition(self.toonsB, self.battleBNode),
                                            Sequence(Wait(2),
                                                     Func(self.setChatAbsolute, attackToons, CFSpeech)))))))
        track.append(dialogTrack)
        return Sequence(Func(self.stickToonsToFloor), track, Func(self.unstickToons),
                        name=self.uniqueName('Introduction'))

    def __makeRollToBattleTwoMovie(self):
        startPos = Point3(SellbotBossBattleOnePosHpr[0:3])
        if self.arenaSide:
            topRampPos = Point3(*SellbotBossTopRampPosB)
            topRampTurnPos = Point3(*SellbotBossTopRampTurnPosB)
            p3Pos = Point3(*SellbotBossP3PosB)
        else:
            topRampPos = Point3(*SellbotBossTopRampPosA)
            topRampTurnPos = Point3(*SellbotBossTopRampTurnPosA)
            p3Pos = Point3(*SellbotBossP3PosA)
        battlePos = Point3(SellbotBossBattleTwoPosHpr[0:3])
        battleHpr = VBase3(SellbotBossBattleTwoPosHpr[3:6])
        bossTrack = Sequence()
        bossTrack.append(Func(self.getGeomNode().setH, 180))
        bossTrack.append(Func(self.loop, 'Fb_neutral'))
        track, hpr = self.rollBossToPoint(startPos, None, topRampPos, None, 0)
        bossTrack.append(track)
        track, hpr = self.rollBossToPoint(topRampPos, hpr, topRampTurnPos, None, 0)
        bossTrack.append(track)
        track, hpr = self.rollBossToPoint(topRampTurnPos, hpr, p3Pos, None, 0)
        bossTrack.append(track)
        track, hpr = self.rollBossToPoint(p3Pos, hpr, battlePos, None, 0)
        bossTrack.append(track)
        return Sequence(bossTrack, Func(self.getGeomNode().setH, 0), name=self.uniqueName('BattleTwo'))

    def cagedToonMovieFunction(self, instruct, cageIndex):
        self.notify.debug('cagedToonMovieFunction()')
        if not (hasattr(self, 'cagedToon') and hasattr(self.cagedToon, 'nametag') and hasattr(self.cagedToon,
                                                                                              'nametag3d')):
            return
        if instruct == 1:
            self.cagedToon.nametag3d.setScale(2)
        elif instruct == 2:
            self.cagedToon.setChatAbsolute(TTLocalizer.CagedToonDrop[cageIndex], CFSpeech)
        elif instruct == 3:
            self.cagedToon.nametag3d.setScale(1)
        elif instruct == 4:
            self.cagedToon.clearChat()

    def makeEndOfBattleMovie(self, hasLocalToon):
        name = self.uniqueName('CageDrop')
        seq = Sequence(name=name)
        seq.append(Func(self.cage1.setPos, self.cagePos[self.cageIndex]))
        if hasLocalToon:
            seq += [Func(camera.reparentTo, render),
                    Func(camera.setPosHpr, self.cage1, 0, -50, 0, 0, 0, 0),
                    Func(localAvatar.setCameraFov, ToontownGlobals.CogHQCameraFov),
                    Func(self.hide)]
        seq += [Wait(0.5),
                Parallel(self.cage1.posInterval(1, self.cagePos[self.cageIndex + 1], blendType='easeInOut'),
                         SoundInterval(self.cageLowerSfx, duration=1)),
                Func(self.cagedToonMovieFunction, 1, self.cageIndex),
                Func(self.cagedToonMovieFunction, 2, self.cageIndex),
                Wait(3),
                Func(self.cagedToonMovieFunction, 3, self.cageIndex),
                Func(self.cagedToonMovieFunction, 4, self.cageIndex)]
        if hasLocalToon:
            seq += [Func(self.show),
                    Func(camera.reparentTo, localAvatar),
                    Func(camera.setPos, localAvatar.cameraPositions[0][0]),
                    Func(camera.setHpr, 0, 0, 0)]
        self.cageIndex += 1
        return seq

    def __makeBossDamageMovie(self):
        startPos = Point3(SellbotBossBattleTwoPosHpr[0:3])
        startHpr = Point3(*SellbotBossBattleThreeHpr)
        bottomPos = Point3(*SellbotBossBottomPos)
        deathPos = Point3(*SellbotBossDeathPos)
        self.setPosHpr(startPos, startHpr)
        bossTrack = Sequence()
        bossTrack.append(Func(self.loop, 'Fb_neutral'))
        track, hpr = self.rollBossToPoint(startPos, startHpr, bottomPos, None, 1)
        bossTrack.append(track)
        track, hpr = self.rollBossToPoint(bottomPos, startHpr, deathPos, None, 1)
        bossTrack.append(track)
        return bossTrack

    def __talkAboutPromotion(self, speech):
        if not self.localToonPromoted:
            pass
        elif self.prevCogSuitLevel < ToontownGlobals.MaxCogSuitLevel:
            speech += TTLocalizer.CagedToonPromotion
            newCogSuitLevel = localAvatar.getCogLevels()[CogDisguiseGlobals.dept2deptIndex(self.style.dept)]
            if newCogSuitLevel == ToontownGlobals.MaxCogSuitLevel:
                speech += TTLocalizer.CagedToonLastPromotion % (ToontownGlobals.MaxCogSuitLevel + 1)
            if newCogSuitLevel in ToontownGlobals.CogSuitHPLevels:
                speech += TTLocalizer.CagedToonHPBoost
        else:
            speech += TTLocalizer.CagedToonMaxed % (ToontownGlobals.MaxCogSuitLevel + 1)
        return speech

    def __makeCageOpenMovie(self):
        speech = TTLocalizer.CagedToonThankYou
        speech = self.__talkAboutPromotion(speech)
        name = self.uniqueName('CageOpen')
        seq = Sequence(
            Func(self.cage1.setPos, self.cagePos[4]),
            Func(self.cageDoor.setHpr, VBase3(0, 0, 0)),
            Func(self.cagedToon.setPos, Point3(0, -2, 0)),
            Parallel(
                self.cage1.posInterval(0.5, self.cagePos[5], blendType='easeOut'),
                SoundInterval(self.cageLowerSfx, duration=0.5)),
            Parallel(
                self.cageDoor.hprInterval(0.5, VBase3(0, 90, 0), blendType='easeOut'),
                Sequence(SoundInterval(self.cageDoorSfx), duration=0)),
            Wait(0.2),
            Func(self.cagedToon.loop, 'walk'),
            self.cagedToon.posInterval(0.8, Point3(0, -6, 0)),
            Func(self.cagedToon.setChatAbsolute, TTLocalizer.CagedToonHooray, CFSpeech),
            ActorInterval(self.cagedToon, 'jump'),
            Func(self.cagedToon.loop, 'neutral'),
            Func(self.cagedToon.headsUp, localAvatar),
            Func(self.cagedToon.setLocalPageChat, speech, 0),
            Func(camera.reparentTo, localAvatar),
            Func(camera.setPos, 0, -9, 9),
            Func(camera.lookAt, self.cagedToon, Point3(0, 0, 2)), name=name)
        return seq

    def __showOnscreenMessage(self, text):
        if self.onscreenMessage:
            self.onscreenMessage.destroy()
            self.onscreenMessage = None
        self.onscreenMessage = DirectLabel(text=text, text_fg=VBase4(1, 1, 1, 1), text_align=TextNode.ACenter,
                                           relief=None, pos=(0, 0, 0.35), scale=0.1)
        return

    def __clearOnscreenMessage(self):
        if self.onscreenMessage:
            self.onscreenMessage.destroy()
            self.onscreenMessage = None
        return

    def __showWaitingMessage(self, task):
        self.__showOnscreenMessage(TTLocalizer.BuildingWaitingForVictors)

    def __placeCageShadow(self):
        if self.cageShadow is None:
            self.cageShadow = loader.loadModel('phase_3/models/props/drop_shadow')
            self.cageShadow.setPos(0, 77.9, 18)
            self.cageShadow.setColorScale(1, 1, 1, 0.6)
        self.cageShadow.reparentTo(render)
        return

    def __removeCageShadow(self):
        if self.cageShadow:
            self.cageShadow.detachNode()
        return

    def setCageIndex(self, cageIndex):
        self.cageIndex = cageIndex
        self.cage1.setPos(self.cagePos[self.cageIndex])
        if self.cageIndex >= 4:
            self.__placeCageShadow()
        else:
            self.__removeCageShadow()

    def loadEnvironment(self):
        DistributedBossCog.DistributedBossCog.loadEnvironment(self)
        self.geom = loader.loadModel('phase_9/models/cogHQ/BossRoomHQ')
        self.rampA = self.__findRamp('rampA', '**/west_ramp2')
        self.rampB = self.__findRamp('rampB', '**/west_ramp')
        self.rampC = self.__findRamp('rampC', '**/west_ramp1')
        self.cage1 = self.geom.find('**/cage')
        #self.cage2 = self.geom.find('**/cage2')
        #self.cooler = loader.loadModel('phase_9/models/cogHQ/pieCooler')
        elevatorEntrance = self.geom.find('**/elevatorEntrance')
        elevatorEntrance.getChildren().detach()
        elevatorEntrance.setScale(1)
        elevatorModel = loader.loadModel('phase_9/models/cogHQ/cogHQ_elevator')
        elevatorModel.reparentTo(elevatorEntrance)
        self.setupElevator(elevatorModel)
        pos = self.cage1.getPos()
        self.cagePos = []
        for height in self.cageHeights:
            self.cagePos.append(Point3(pos[0], pos[1], height))

        self.cageDoor = self.geom.find('**/cage_door')
        self.cage1.setScale(1)
        self.rope = Rope.Rope(name='supportChain')
        self.rope.reparentTo(self.cage1)
        self.rope.setup(2, ((self.cage1, (0.15, 0.13, 16)), (self.geom, (0.23, 78, 120))))
        self.rope.ropeNode.setRenderMode(RopeNode.RMBillboard)
        self.rope.ropeNode.setUvMode(RopeNode.UVDistance)
        self.rope.ropeNode.setUvDirection(0)
        self.rope.ropeNode.setUvScale(0.8)
        self.rope.setTexture(self.cage1.findTexture('hq_chain'))
        self.rope.setTransparency(1)
        self.elevatorMusic = base.loader.loadMusic('phase_9/audio/bgm/sb_elevator.ogg')
        self.introMusic = base.loader.loadMusic('phase_9/audio/bgm/encntr_head_suit_theme.ogg')
        self.revealMusic = base.loader.loadMusic('phase_9/audio/bgm/encntr_sting_announce.ogg')
        self.betweenBattleMusic = base.loader.loadMusic('phase_9/audio/bgm/encntr_toon_winning.ogg')
        self.battleTwoMusic = base.loader.loadMusic('phase_9/audio/bgm/encntr_vp_suits.ogg')
        self.battleThreeMusic = base.loader.loadMusic('phase_9/audio/bgm/encntr_vp_pie.ogg')
        self.geom.reparentTo(render)

    def unloadEnvironment(self):
        DistributedBossCog.DistributedBossCog.unloadEnvironment(self)
        self.geom.removeNode()
        del self.geom
        del self.cage1
        self.rampA.requestFinalState()
        self.rampB.requestFinalState()
        self.rampC.requestFinalState()
        del self.rampA
        del self.rampB
        del self.rampC

    def __loadMopaths(self):
        self.toonsEnterA = Mopath.Mopath()
        self.toonsEnterA.loadFile('phase_9/paths/bossBattle-toonsEnterA')
        self.toonsEnterA.fFaceForward = 1
        self.toonsEnterA.timeScale = 35
        self.toonsEnterB = Mopath.Mopath()
        self.toonsEnterB.loadFile('phase_9/paths/bossBattle-toonsEnterB')
        self.toonsEnterB.fFaceForward = 1
        self.toonsEnterB.timeScale = 35

    def __unloadMotionPaths(self):
        self.toonsEnterA.reset()
        self.toonsEnterB.reset()

    def __findRamp(self, name, path):
        ramp = self.geom.find(path)
        children = ramp.getChildren()
        animate = ramp.attachNewNode(name)
        children.reparentTo(animate)
        fsm = ClassicFSM.ClassicFSM(name, [
            State.State('extend',
                        Functor(self.enterRampExtend, animate),
                        Functor(self.exitRampExtend, animate), [
                            'extended',
                            'retract',
                            'retracted']),
            State.State('extended',
                        Functor(self.enterRampExtended, animate),
                        Functor(self.exitRampExtended, animate), [
                            'retract',
                            'retracted']),
            State.State('retract',
                        Functor(self.enterRampRetract, animate),
                        Functor(self.exitRampRetract, animate), [
                            'extend',
                            'extended',
                            'retracted']),
            State.State('retracted',
                        Functor(self.enterRampRetracted, animate),
                        Functor(self.exitRampRetracted, animate), [
                            'extend',
                            'extended']),
            State.State('off',
                        Functor(self.enterRampOff, animate),
                        Functor(self.exitRampOff, animate))],
                                    'off', 'off', onUndefTransition=ClassicFSM.ClassicFSM.DISALLOW)
        fsm.enterInitialState()
        return fsm

    def enterRampExtend(self, animate):
        intervalName = self.uniqueName('extend-%s' % animate.getName())
        adjustTime = 2.0 * animate.getX() / 18.0
        interval = Parallel(SoundInterval(self.rampSlideSfx, node=animate),
                            animate.posInterval(adjustTime, Point3(0, 0, 0), blendType='easeInOut', name=intervalName))
        interval.start()
        self.storeInterval(interval, intervalName)

    def exitRampExtend(self, animate):
        intervalName = self.uniqueName('extend-%s' % animate.getName())
        self.clearInterval(intervalName)

    def enterRampExtended(self, animate):
        animate.setPos(0, 0, 0)

    def exitRampExtended(self, animate):
        pass

    def enterRampRetract(self, animate):
        intervalName = self.uniqueName('retract-%s' % animate.getName())
        adjustTime = 2.0 * (18 - animate.getX()) / 18.0
        interval = Parallel(SoundInterval(self.rampSlideSfx, node=animate),
                            animate.posInterval(adjustTime, Point3(18, 0, 0), blendType='easeInOut', name=intervalName))
        interval.start()
        self.storeInterval(interval, intervalName)

    def exitRampRetract(self, animate):
        intervalName = self.uniqueName('retract-%s' % animate.getName())
        self.clearInterval(intervalName)

    def enterRampRetracted(self, animate):
        animate.setPos(18, 0, 0)

    def exitRampRetracted(self, animate):
        pass

    def enterRampOff(self, animate):
        pass

    def exitRampOff(self, animate):
        pass

    def enterOff(self):
        DistributedBossCog.DistributedBossCog.enterOff(self)
        if self.cagedToon:
            self.cagedToon.clearChat()
        if self.rampA:
            self.rampA.request('off')
        if self.rampB:
            self.rampB.request('off')
        if self.rampC:
            self.rampC.request('off')

    def enterWaitForToons(self):
        DistributedBossCog.DistributedBossCog.enterWaitForToons(self)
        self.geom.hide()
        self.cagedToon.removeActive()

    def exitWaitForToons(self):
        DistributedBossCog.DistributedBossCog.exitWaitForToons(self)
        self.geom.show()
        self.cagedToon.addActive()

    def enterElevator(self):
        DistributedBossCog.DistributedBossCog.enterElevator(self)
        self.rampA.request('extended')
        self.rampB.request('extended')
        self.rampC.request('retracted')
        self.setCageIndex(0)
        self.reparentTo(render)
        self.setPosHpr(*SellbotBossBattleOnePosHpr)
        self.happy = 1
        self.raised = 1
        self.forward = 1
        self.doAnimate()
        self.cagedToon.removeActive()

    def exitElevator(self):
        DistributedBossCog.DistributedBossCog.exitElevator(self)
        self.cagedToon.addActive()

    def enterIntroduction(self):
        self.reparentTo(render)
        self.setPosHpr(*SellbotBossBattleOnePosHpr)
        self.stopAnimate()
        DistributedBossCog.DistributedBossCog.enterIntroduction(self)
        self.rampA.request('extended')
        self.rampB.request('extended')
        self.rampC.request('retracted')
        self.setCageIndex(0)
        base.playMusic(self.introMusic, looping=0, volume=1)

    def exitIntroduction(self):
        DistributedBossCog.DistributedBossCog.exitIntroduction(self)
        self.introMusic.stop()

    def enterBattleOne(self):
        DistributedBossCog.DistributedBossCog.enterBattleOne(self)
        self.reparentTo(render)
        self.setPosHpr(*SellbotBossBattleOnePosHpr)
        self.clearChat()
        self.cagedToon.clearChat()
        self.rampA.request('retract')
        self.rampB.request('retract')
        self.rampC.request('retract')
        if self.battleA is None or self.battleB is None:
            cageIndex = 1
        else:
            cageIndex = 0
        self.setCageIndex(cageIndex)
        return

    def exitBattleOne(self):
        DistributedBossCog.DistributedBossCog.exitBattleOne(self)

    def enterRollToBattleTwo(self):
        self.disableToonCollision()
        self.releaseToons()
        if self.arenaSide:
            self.rampA.request('retract')
            self.rampB.request('extend')
        else:
            self.rampA.request('extend')
            self.rampB.request('retract')
        self.rampC.request('retract')
        self.reparentTo(render)
        self.setCageIndex(2)
        self.stickBossToFloor()
        intervalName = 'RollToBattleTwo'
        seq = Sequence(self.__makeRollToBattleTwoMovie(), Func(self.__onToPrepareBattleTwo), name=intervalName)
        seq.start()
        self.storeInterval(seq, intervalName)
        base.playMusic(self.betweenBattleMusic, looping=1, volume=0.9)
        self.__showEasyBarrels()
        taskMgr.doMethodLater(0.5, self.enableToonCollision, 'enableToonCollision')

    def __onToPrepareBattleTwo(self):
        self.disableToonCollision()
        self.unstickBoss()
        self.setPosHpr(*SellbotBossBattleTwoPosHpr)
        self.doneBarrier('RollToBattleTwo')

    def exitRollToBattleTwo(self):
        self.unstickBoss()
        intervalName = 'RollToBattleTwo'
        self.clearInterval(intervalName)
        self.betweenBattleMusic.stop()

    def disableToonCollision(self):
        base.localAvatar.collisionsOff()

    def enableToonCollision(self, task):
        base.localAvatar.collisionsOn()

    def enterPrepareBattleTwo(self):
        self.cleanupIntervals()
        self.__hideEasyBarrels()
        self.controlToons()
        self.clearChat()
        self.cagedToon.clearChat()
        self.reparentTo(render)
        if self.arenaSide:
            self.rampA.request('retract')
            self.rampB.request('extend')
        else:
            self.rampA.request('extend')
            self.rampB.request('retract')
        self.rampC.request('retract')
        self.reparentTo(render)
        self.setCageIndex(2)
        camera.reparentTo(render)
        camera.setPosHpr(self.cage1, 0, -17, 3.3, 0, 0, 0)
        (localAvatar.setCameraFov(ToontownGlobals.CogHQCameraFov),)
        self.hide()
        self.acceptOnce('doneChatPage', self.__onToBattleTwo)
        self.cagedToon.setLocalPageChat(TTLocalizer.CagedToonMiniCogInfo, 1)
        base.playMusic(self.stingMusic, looping=0, volume=1.0)
        taskMgr.doMethodLater(0.5, self.enableToonCollision, 'enableToonCollision')

    def __onToBattleTwo(self, elapsed):
        self.doneBarrier('PrepareBattleTwo')
        taskMgr.doMethodLater(1, self.__showWaitingMessage, self.uniqueName('WaitingMessage'))

    def exitPrepareBattleTwo(self):
        self.show()
        taskMgr.remove(self.uniqueName('WaitingMessage'))
        self.ignore('doneChatPage')
        self.__clearOnscreenMessage()
        self.stingMusic.stop()

    def enterBattleTwo(self):
        self.cleanupIntervals()
        mult = ToontownBattleGlobals.getBossBattleCreditMultiplier(2)
        localAvatar.inventory.setBattleCreditMultiplier(mult)
        self.reparentTo(render)
        self.setPosHpr(*SellbotBossBattleTwoPosHpr)
        self.clearChat()
        self.cagedToon.clearChat()
        self.rampA.request('retract')
        self.rampB.request('retract')
        self.rampC.request('retract')
        self.releaseToons()
        self.toonsToBattlePosition(self.toonsA, self.battleANode)
        self.toonsToBattlePosition(self.toonsB, self.battleBNode)
        if self.battleA is None or self.battleB is None:
            cageIndex = 3
        else:
            cageIndex = 2
        self.setCageIndex(cageIndex)
        base.playMusic(self.battleTwoMusic, looping=1, volume=0.9)
        return

    def exitBattleTwo(self):
        intervalName = self.uniqueName('cageDrop')
        self.clearInterval(intervalName)
        self.cleanupBattles()
        self.battleTwoMusic.stop()
        localAvatar.inventory.setBattleCreditMultiplier(1)

    def enterPrepareBattleThree(self):
        self.cleanupIntervals()
        self.controlToons()
        self.clearChat()
        self.cagedToon.clearChat()
        self.reparentTo(render)
        self.rampA.request('retract')
        self.rampB.request('retract')
        self.rampC.request('extend')
        self.setCageIndex(4)
        camera.reparentTo(render)
        camera.setPosHpr(self.cage1, 0, -17, 3.3, 0, 0, 0)
        (localAvatar.setCameraFov(ToontownGlobals.CogHQCameraFov),)
        self.hide()
        self.acceptOnce('doneChatPage', self.__onToBattleThree)
        self.cagedToon.setLocalPageChat(TTLocalizer.CagedToonPrepareBattleThree, 1)
        base.playMusic(self.betweenBattleMusic, looping=1, volume=0.9)

    def __onToBattleThree(self, elapsed):
        self.doneBarrier('PrepareBattleThree')
        taskMgr.doMethodLater(1, self.__showWaitingMessage, self.uniqueName('WaitingMessage'))

    def exitPrepareBattleThree(self):
        self.show()
        taskMgr.remove(self.uniqueName('WaitingMessage'))
        self.ignore('doneChatPage')
        intervalName = 'PrepareBattleThree'
        self.clearInterval(intervalName)
        self.__clearOnscreenMessage()
        self.betweenBattleMusic.stop()

    def enterBattleThree(self):
        DistributedBossCog.DistributedBossCog.enterBattleThree(self)
        self.clearChat()
        self.cagedToon.clearChat()
        self.reparentTo(render)
        self.rampA.request('retract')
        self.rampB.request('retract')
        self.rampC.request('extend')
        self.setCageIndex(4)
        self.happy = 0
        self.raised = 1
        self.forward = 1
        self.doAnimate()
        self.accept('enterCage', self.__touchedCage)
        self.accept('pieSplat', self.__pieSplat)
        self.accept('localPieSplat', self.__localPieSplat)
        self.accept('outOfPies', self.__outOfPies)
        self.accept('begin-pie', self.__foundPieButton)
        localAvatar.setCameraFov(ToontownGlobals.BossBattleCameraFov)
        taskMgr.doMethodLater(30, self.__howToGetPies, self.uniqueName('PieAdvice'))
        self.stickBossToFloor()
        self.bossDamageMovie = self.__makeBossDamageMovie()
        bossDoneEventName = self.uniqueName('DestroyedBoss')
        self.bossDamageMovie.setDoneEvent(bossDoneEventName)
        self.acceptOnce(bossDoneEventName, self.__doneBattleThree)
        self.resetMaxDamage()
        self.bossDamageToMovie = self.bossDamageMovie.getDuration() / self.bossMaxDamage
        self.bossDamageMovie.setT(self.bossDamage * self.bossDamageToMovie)
        base.playMusic(self.battleThreeMusic, looping=1, volume=0.9)
        self.bossHealthBar.initialize(self.bossMaxDamage - self.bossDamage, self.bossMaxDamage)

    def __doneBattleThree(self):
        self.setState('Victory')
        self.unstickBoss()

    def exitBattleThree(self):
        DistributedBossCog.DistributedBossCog.exitBattleThree(self)
        bossDoneEventName = self.uniqueName('DestroyedBoss')
        self.ignore(bossDoneEventName)
        taskMgr.remove(self.uniqueName('StandUp'))
        self.ignore('enterCage')
        self.ignore('pieSplat')
        self.ignore('localPieSplat')
        self.ignore('outOfPies')
        self.ignore('begin-pie')
        self.__clearOnscreenMessage()
        taskMgr.remove(self.uniqueName('PieAdvice'))
        localAvatar.setCameraFov(ToontownGlobals.CogHQCameraFov)
        self.__removeCageShadow()
        self.bossDamageMovie.finish()
        self.bossDamageMovie = None
        self.unstickBoss()
        taskName = 'RecoverBossDamage'
        taskMgr.remove(taskName)
        self.battleThreeMusicTime = self.battleThreeMusic.getTime()
        self.battleThreeMusic.stop()
        return

    def enterVictory(self):
        self.cleanupIntervals()
        localAvatar.setCameraFov(ToontownGlobals.BossBattleCameraFov)
        self.reparentTo(render)
        self.setPos(*SellbotBossDeathPos)
        self.setHpr(*SellbotBossBattleThreeHpr)
        self.clearChat()
        self.cagedToon.clearChat()
        self.setCageIndex(4)
        self.releaseToons(finalBattle=1)
        self.rampA.request('retract')
        self.rampB.request('retract')
        self.rampC.request('extend')
        self.happy = 0
        self.raised = 0
        self.forward = 1
        self.doAnimate('Fb_fall', now=1)
        self.acceptOnce(self.animDoneEvent, self.__continueVictory)
        self.bossHealthBar.deinitialize()
        base.playMusic(self.battleThreeMusic, looping=1, volume=0.9, time=self.battleThreeMusicTime)

    def __continueVictory(self):
        self.stopAnimate()
        self.stash()
        self.doneBarrier('Victory')

    def exitVictory(self):
        self.stopAnimate()
        self.unstash()
        self.__removeCageShadow()
        localAvatar.setCameraFov(ToontownGlobals.CogHQCameraFov)
        self.battleThreeMusicTime = self.battleThreeMusic.getTime()
        self.battleThreeMusic.stop()

    def enterReward(self):
        self.cleanupIntervals()
        self.clearChat()
        self.cagedToon.clearChat()
        self.stash()
        self.stopAnimate()
        self.setCageIndex(4)
        self.releaseToons(finalBattle=1)
        self.toMovieMode()
        self.rampA.request('retract')
        self.rampB.request('retract')
        self.rampC.request('extend')
        panelName = self.uniqueName('reward')
        self.rewardPanel = RewardPanel.RewardPanel(panelName)
        victory, camVictory, skipper = MovieToonVictory.doToonVictory(1, self.involvedToons, self.toonRewardIds,
                                                                      self.toonRewardDicts, self.deathList,
                                                                      self.rewardPanel, allowGroupShot=0, noSkip=True)
        interval = Sequence(Parallel(victory, camVictory), Func(self.__doneReward))
        intervalName = 'RewardMovie'
        delayDeletes = []
        for toonId in self.involvedToons:
            toon = self.cr.doId2do.get(toonId)
            if toon:
                delayDeletes.append(DelayDelete.DelayDelete(toon, 'SellbotBoss.enterReward'))

        interval.delayDeletes = delayDeletes
        interval.start()
        self.storeInterval(interval, intervalName)
        base.playMusic(self.battleThreeMusic, looping=1, volume=0.9, time=self.battleThreeMusicTime)

    def __doneReward(self):
        self.doneBarrier('Reward')
        self.toWalkMode()

    def exitReward(self):
        intervalName = 'RewardMovie'
        self.clearInterval(intervalName)
        self.unstash()
        self.rewardPanel.destroy()
        del self.rewardPanel
        self.__removeCageShadow()
        self.battleThreeMusicTime = 0
        self.battleThreeMusic.stop()

    def enterEpilogue(self):
        self.cleanupIntervals()
        self.clearChat()
        self.cagedToon.clearChat()
        self.stash()
        self.stopAnimate()
        self.setCageIndex(4)
        self.controlToons()
        self.rampA.request('retract')
        self.rampB.request('retract')
        self.rampC.request('extend')
        self.__arrangeToonsAroundCage()
        camera.reparentTo(render)
        camera.setPosHpr(-24, 52, 27.5, -53, -13, 0)
        intervalName = 'EpilogueMovie'
        seq = Sequence(self.__makeCageOpenMovie(), name=intervalName)
        seq.start()
        self.storeInterval(seq, intervalName)
        self.accept('nextChatPage', self.__epilogueChatNext)
        self.accept('doneChatPage', self.__epilogueChatDone)
        base.playMusic(self.epilogueMusic, looping=1, volume=0.9)

    def __epilogueChatNext(self, pageNumber, elapsed):
        pass

    def __epilogueChatDone(self, elapsed):
        self.cagedToon.setChatAbsolute(TTLocalizer.CagedToonGoodbye, CFSpeech)
        self.ignore('nextChatPage')
        self.ignore('doneChatPage')
        intervalName = 'EpilogueMovieToonAnim'
        self.clearInterval(intervalName)
        track = Parallel(Sequence(ActorInterval(self.cagedToon, 'wave'), Func(self.cagedToon.loop, 'neutral')),
                         Sequence(Wait(0.5), Func(self.localToonToSafeZone)))
        self.storeInterval(track, intervalName)
        track.start()

    def exitEpilogue(self):
        self.clearInterval('EpilogueMovieToonAnim')
        self.unstash()
        self.__removeCageShadow()
        self.epilogueMusic.stop()

    def __arrangeToonsAroundCage(self):
        radius = 15
        numToons = len(self.involvedToons)
        center = (numToons - 1) / 2.0
        for i in xrange(numToons):
            toon = base.cr.doId2do.get(self.involvedToons[i])
            if toon:
                angle = 270 - 15 * (i - center)
                radians = angle * math.pi / 180.0
                x = math.cos(radians) * radius
                y = math.sin(radians) * radius
                toon.setPos(self.cage1, x, y, 0)
                toon.setZ(18.0)
                toon.headsUp(self.cage1)

    def enterFrolic(self):
        DistributedBossCog.DistributedBossCog.enterFrolic(self)
        self.setPosHpr(*SellbotBossBattleOnePosHpr)

    def doorACallback(self, isOpen):
        if self.insidesANodePath:
            if isOpen:
                self.insidesANodePath.unstash()
            else:
                self.insidesANodePath.stash()

    def doorBCallback(self, isOpen):
        if self.insidesBNodePath:
            if isOpen:
                self.insidesBNodePath.unstash()
            else:
                self.insidesBNodePath.stash()

    def __toonsToPromotionPosition(self, toonIds, battleNode):
        points = BattleBase.BattleBase.toonPoints[len(toonIds) - 1]
        for i in xrange(len(toonIds)):
            toon = base.cr.doId2do.get(toonIds[i])
            if toon:
                toon.reparentTo(render)
                pos, h = points[i]
                toon.setPosHpr(battleNode, pos[0], pos[1] + 10, pos[2], h, 0, 0)

    def __doobersToPromotionPosition(self, doobers, battleNode):
        points = BattleBase.BattleBase.toonPoints[len(doobers) - 1]
        for i in xrange(len(doobers)):
            suit = doobers[i]
            suit.fsm.request('neutral')
            suit.loop('neutral')
            pos, h = points[i]
            suit.setPosHpr(battleNode, pos[0], pos[1] + 10, pos[2], h, 0, 0)

    def __touchedCage(self, entry):
        self.sendUpdate('touchCage', [])
        self.__clearOnscreenMessage()
        taskMgr.remove(self.uniqueName('PieAdvice'))
        base.playSfx(self.piesRestockSfx)
        if not self.everThrownPie:
            taskMgr.doMethodLater(30, self.__howToThrowPies, self.uniqueName('PieAdvice'))

    def __outOfPies(self):
        self.__showOnscreenMessage(TTLocalizer.BossBattleNeedMoreGags)
        taskMgr.doMethodLater(20, self.__howToGetPies, self.uniqueName('PieAdvice'))

    def __howToGetPies(self, task):
        self.__showOnscreenMessage(TTLocalizer.BossBattleHowToGetSlices)

    def __howToThrowPies(self, task):
        self.__showOnscreenMessage(TTLocalizer.BossBattleHowToThrow)

    def __foundPieButton(self):
        self.everThrownPie = 1
        self.__clearOnscreenMessage()
        taskMgr.remove(self.uniqueName('PieAdvice'))

    def __pieSplat(self, toon, pieCode):
        if base.config.GetBool('easy-vp', 0):
            if not self.dizzy:
                pieCode = ToontownGlobals.PieCodeBossInsides
        if pieCode == ToontownGlobals.PieCodeBossInsides:
            if toon == localAvatar:
                self.d_hitBossInsides()
                self.bossHealthBar.updateStunCount(toon.doId)
            self.flashRed()
        elif pieCode == ToontownGlobals.PieCodeBossCog:
            if self.dizzy:
                pieDamage = getPieDamage(self.battleTier, toon)
                self.b_hitBoss(pieDamage, toon)

    def __localPieSplat(self, pieCode, entry):
        if pieCode != ToontownGlobals.PieCodeToon:
            return
        avatarDoId = entry.getIntoNodePath().getNetTag('avatarDoId')
        if avatarDoId == '':
            self.notify.warning('Toon %s has no avatarDoId tag.' % repr(entry.getIntoNodePath()))
            return
        doId = int(avatarDoId)
        if doId != localAvatar.doId:
            self.d_hitToon(doId)

    def cagedToonBattleThree(self, index, avId):
        str = TTLocalizer.CagedToonBattleThree.get(index)
        if str:
            toonName = ''
            if avId:
                toon = self.cr.doId2do.get(avId)
                if not toon:
                    self.cagedToon.clearChat()
                    return
                toonName = toon.getName()
            text = str % {'toon': toonName}
            self.cagedToon.setChatAbsolute(text, CFSpeech | CFTimeout)
        else:
            self.cagedToon.clearChat()

    def cleanupAttacks(self):
        self.__cleanupStrafe()

    def __cleanupStrafe(self):
        if self.strafeInterval:
            self.strafeInterval.finish()
            self.strafeInterval = None
        return

    def doStrafe(self, side, direction):
        gearRoot = self.rotateNode.attachNewNode('gearRoot')
        if side == 0:
            gearRoot.setPos(0, -7, 3)
            gearRoot.setHpr(180, 0, 0)
            door = self.doorA
        else:
            gearRoot.setPos(0, 7, 3)
            door = self.doorB
        gearRoot.setTag('attackCode', str(ToontownGlobals.BossCogStrafeAttack))
        gearModel = self.getGearFrisbee()
        gearModel.setScale(StrafeGearSizes[self.battleTier])
        t = self.getBossDamage() / self.bossMaxDamage
        gearTrack = Parallel()
        numGears = int(math.ceil(4 + 6 * t) * StrafeGearCount[self.battleTier])
        time = (5.0 - 4.0 * t) * StrafeGearTime[self.battleTier]
        spread = math.pi * StrafeSpreadAngles[self.battleTier] / 180.0
        if direction == 1:
            spread = -spread
        dist = 50
        rate = time / numGears
        loops = max(1, self.battleTier)
        gearsPerWave = numGears / loops
        for i in xrange(loops):
            for j in xrange(gearsPerWave):
                delay = (j + gearsPerWave * i) * rate
                node = gearRoot.attachNewNode(str(j))
                node.hide()
                node.setPos(0, 0, 0)
                gear = gearModel.instanceTo(node)
                angle = (float(j) / (gearsPerWave - 1) - 0.5) * spread
                x = dist * math.sin(angle)
                y = dist * math.cos(angle)
                h = random.uniform(-720, 720)
                gearTrack.append(Sequence(Wait(delay), Func(node.show),
                                          Parallel(node.posInterval(1, Point3(x, y, 0), fluid=1),
                                                   node.hprInterval(1, VBase3(h, 0, 0), fluid=1),
                                                   Sequence(SoundInterval(self.strafeSfx[j % len(self.strafeSfx)], volume=0.2, node=self),
                                                            duration=0)), Func(node.detachNode)))
            spread = -spread

        seq = Sequence(Func(door.request, 'open'), Wait(0.7), gearTrack, Func(door.request, 'close'))
        self.__cleanupStrafe()
        self.strafeInterval = seq
        seq.start()

    def __showEasyBarrels(self):
        barrelNodes = hidden.findAllMatches('**/Distributed*Barrel-*')
        if not barrelNodes or barrelNodes.isEmpty():
            return
        if render.find('barrelsRootNode'):
            self.notify.warning('__showEasyBarrels(): barrelsRootNode already exists')
            return
        self.barrelsRootNode = render.attachNewNode('barrelsRootNode')
        self.barrelsRootNode.setPos(*BarrelsStartPos)
        if self.arenaSide == 0:
            self.barrelsRootNode.setHpr(180, 0, 0)
        else:
            self.barrelsRootNode.setHpr(0, 0, 0)
        for i, barrelNode in enumerate(barrelNodes):
            barrel = base.cr.doId2do.get(int(barrelNode.getNetTag('doId')))
            setBarrelAttr(barrel, barrel.entId)
            if hasattr(barrel, 'applyLabel'):
                barrel.applyLabel()
            barrel.setPosHpr(barrel.pos, barrel.hpr)
            barrel.reparentTo(self.barrelsRootNode)

        intervalName = 'MakeBarrelsAppear'
        seq = Sequence(LerpPosInterval(self.barrelsRootNode, 0.5, Vec3(*BarrelsFinalPos),
                                       blendType='easeInOut'), name=intervalName)
        seq.start()
        self.storeInterval(seq, intervalName)

    def __hideEasyBarrels(self):
        if hasattr(self, 'barrelsRootNode'):
            self.barrelsRootNode.removeNode()
            intervalName = 'MakeBarrelsAppear'
            self.clearInterval(intervalName)

    def toonPromoted(self, promoted):
        self.localToonPromoted = promoted
