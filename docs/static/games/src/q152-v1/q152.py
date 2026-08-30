"""q152 Shadows to Forces -- transfer a geometric offset rule into invisible force control."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LESSON,FIELD,OBJECT,SHADOW,BODY,TARGET,DONE,BAD=9,1,12,14,3,6,11,15,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS=[
 {"name":"One Offset","forces":[4]},
 {"name":"Orthogonal Transfer","forces":[1,4]},
 {"name":"Alternating Attraction","forces":[3,1,4]},
 {"name":"Four Relations","forces":[1,4,2,3]},
 {"name":"Hidden Field","forces":[4,1,3,2,4]},
 {"name":"Shadows to Forces","forces":[1,3,2,4,1,4]},
]


class Display(RenderableUserDisplay):
 def __init__(self,game):self.game=game
 def render_interface(self,frame:np.ndarray)->np.ndarray:
  g=self.game;frame[:,:]=BG;frame[6:29,4:60]=LESSON;frame[34:58,4:60]=FIELD
  if g.index<len(g.forces):
   a=g.forces[g.index];dx,dy=DIRS[a];frame[14:21,20:27]=OBJECT;frame[14+dy*8:21+dy*8,20+dx*8:27+dx*8]=SHADOW;frame[42:50,20:28]=BODY;frame[42+dy*10:50+dy*10,45+dx*5:53+dx*5]=TARGET
  for i in range(len(g.forces)):frame[60:63,6+i*8:12+i*8]=DONE if i<g.index else SHADOW
  if g.failed:frame[30:34,25:39]=BAD
  return frame


class Q152(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.forces=[];self.index=0;self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q152",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[1,2,3,4])
 def on_set_level(self,level):self.forces=list(LEVELS[self.level_index]["forces"]);self.index=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=self.forces[self.index]:self.failed=True;self.lose()
  else:
   self.index+=1
   if self.index==len(self.forces):self.next_level()
  self.complete_action()
