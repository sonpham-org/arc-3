"""q132 Shape-Free Code -- communicate commands through relative marker geometry."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,PAD,ANCHOR,MARKER,RECEIVER,TRAIL,GOAL,BAD=10,1,13,6,9,12,14,8
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS=[
 {"name":"Relative Right","route":[4]},
 {"name":"Two Positions","route":[1,4]},
 {"name":"Corner Phrase","route":[3,1,4]},
 {"name":"Return Signal","route":[1,4,2,3]},
 {"name":"Geometric Sentence","route":[4,1,3,2,4]},
 {"name":"Shape-Free Code","route":[1,4,2,4,3,1]},
]


class Display(RenderableUserDisplay):
 def __init__(self,game):self.game=game
 def render_interface(self,frame:np.ndarray)->np.ndarray:
  g=self.game;frame[:,:]=BG;frame[7:39,5:37]=PAD
  for y in range(3):
   for x in range(3):frame[10+y*9:16+y*9,8+x*9:14+x*9]=TRAIL
  frame[19:27,17:25]=ANCHOR;frame[21+g.offset[1]*9:25+g.offset[1]*9,19+g.offset[0]*9:23+g.offset[0]*9]=MARKER
  frame[10:54,43:59]=PAD;frame[45:51,48:54]=RECEIVER
  for i in range(len(g.route)):frame[5+i*7:10+i*7,48:54]=GOAL if i<g.progress else TRAIL
  if g.failed:frame[58:63,24:40]=BAD
  return frame


class Q132(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.progress=0;self.offset=(0,0);self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q132",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[1,2,3,4,5])
 def on_set_level(self,level):
  self.route=list(LEVELS[self.level_index]["route"]);self.progress=0;self.offset=(0,0);self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in DIRS:
   dx,dy=DIRS[a];self.offset=(max(-1,min(1,self.offset[0]+dx)),max(-1,min(1,self.offset[1]+dy)))
  elif a==5:
   if self.offset!=DIRS[self.route[self.progress]]:self.failed=True;self.lose()
   else:
    self.progress+=1;self.offset=(0,0)
    if self.progress==len(self.route):self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()
