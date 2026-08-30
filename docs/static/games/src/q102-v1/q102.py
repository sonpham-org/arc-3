"""q102 Walking Room -- navigate within a chamber that also walks through the world."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame, Camera, Level, RenderableUserDisplay

CELL, OX, OY, WORLD, ROOM = 7, 8, 10, 7, 3
BG, FIELD, CHAMBER, WALL, PLAYER, GOAL, FACING, BAD = 12, 1, 10, 3, 6, 14, 9, 8
DIRS = {1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS = [
    {"name":"Walk Inside","origin":(1,1),"local":(0,1),"goal":(3,2),"walls":[],"budget":5},
    {"name":"Move the Room","origin":(0,2),"local":(2,1),"goal":(5,3),"walls":[],"budget":8},
    {"name":"Two Scales","origin":(1,3),"local":(0,0),"goal":(5,1),"walls":[(3,3)],"budget":12},
    {"name":"Chamber Wall","origin":(3,0),"local":(1,2),"goal":(1,5),"walls":[(4,3),(3,3)],"budget":15},
    {"name":"Carried Position","origin":(0,0),"local":(2,2),"goal":(6,6),"walls":[(3,2),(2,4)],"budget":18},
    {"name":"Walking Room","origin":(2,2),"local":(1,1),"goal":(0,6),"walls":[(2,4),(3,4),(4,1)],"budget":22},
]


class Display(RenderableUserDisplay):
    def __init__(self,game): self.game=game
    @staticmethod
    def fill(frame,cell,color,inset=0):
        x,y=cell; px,py=OX+x*CELL,OY+y*CELL; frame[py+inset:py+CELL-inset,px+inset:px+CELL-inset]=color
    def render_interface(self,frame:np.ndarray)->np.ndarray:
        g=self.game; frame[:,:]=BG
        for y in range(WORLD):
            for x in range(WORLD): self.fill(frame,(x,y),FIELD,1)
        for wall in g.walls:self.fill(frame,wall,WALL,1)
        ox,oy=g.origin
        for y in range(ROOM):
            for x in range(ROOM): self.fill(frame,(ox+x,oy+y),CHAMBER,1)
        self.fill(frame,g.goal,GOAL,1); self.fill(frame,g.goal,FIELD,3); self.fill(frame,g.world_pos(),PLAYER,1)
        dx,dy=DIRS[g.facing]; frame[3+dy*2:6+dy*2,30+dx*5:34+dx*5]=FACING
        if g.failed:frame[60:63,25:39]=BAD
        return frame


class Q102(ARCBaseGame):
    def __init__(self):
        self.display=Display(self); self.origin=self.local=self.goal=(0,0); self.walls=set(); self.facing=self.budget_left=0; self.failed=False
        levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
        super().__init__("q102",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[1,2,3,4,5])
    def world_pos(self):return self.origin[0]+self.local[0],self.origin[1]+self.local[1]
    def on_set_level(self,level):
        s=LEVELS[self.level_index]; self.origin=tuple(s["origin"]); self.local=tuple(s["local"]); self.goal=tuple(s["goal"]); self.walls=set(map(tuple,s["walls"])); self.facing=4; self.budget_left=s["budget"]; self.failed=False
    def step(self):
        action=self.action.id.value
        if action==0:self.complete_action();return
        self.budget_left-=1
        if action in DIRS:
            self.facing=action; dx,dy=DIRS[action]; local=(self.local[0]+dx,self.local[1]+dy); world=(self.origin[0]+local[0],self.origin[1]+local[1])
            if 0<=local[0]<ROOM and 0<=local[1]<ROOM and world not in self.walls:self.local=local
        elif action==5:
            dx,dy=DIRS[self.facing]; origin=(self.origin[0]+dx,self.origin[1]+dy); world=(origin[0]+self.local[0],origin[1]+self.local[1])
            if 0<=origin[0]<=WORLD-ROOM and 0<=origin[1]<=WORLD-ROOM and world not in self.walls:self.origin=origin
        else:self.failed=True;self.lose()
        if self.world_pos()==self.goal:self.next_level()
        elif self.budget_left<=0:self.failed=True;self.lose()
        self.complete_action()
