from toontown.coghq.SpecImports import *
import random

CogParent1 = 110600
Battle1CellId = 0
BattleCells = {Battle1CellId: {'parentEntId': CogParent1,
                               'pos': Point3(-30.702, 0, 0)}}
CogData = [{'parentEntId': CogParent1,
            'boss': 0,
            'level': random.choice([5, 6, 7]),
            'battleCell': Battle1CellId,
            'pos': Point3(0, -6, 0),
            'h': 90,
            'behavior': 'stand',
            'path': None,
            'skeleton': random.choice([0, 1])},
           {'parentEntId': CogParent1,
            'boss': 0,
            'level': random.choice([5, 6, 7]),
            'battleCell': Battle1CellId,
            'pos': Point3(0, -2, 0),
            'h': 90,
            'behavior': 'stand',
            'path': None,
            'skeleton': random.choice([0, 1])},
           {'parentEntId': CogParent1,
            'boss': 0,
            'level': random.choice([5, 6, 7]),
            'battleCell': Battle1CellId,
            'pos': Point3(-54.404, -2, 0),
            'h': 270,
            'behavior': 'stand',
            'path': None,
            'skeleton': random.choice([0, 1])},
           {'parentEntId': CogParent1,
            'boss': 0,
            'level': random.choice([5, 6, 7]),
            'battleCell': Battle1CellId,
            'pos': Point3(-54.404, -6, 0),
            'h': 270,
            'behavior': 'stand',
            'path': None,
            'skeleton': random.choice([0, 1])}]
ReserveCogData = []
