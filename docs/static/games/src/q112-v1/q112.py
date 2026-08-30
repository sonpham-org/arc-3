"""q112 Negative Demonstration -- infer a policy from paired success and failure traces."""

from __future__ import annotations
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,PANEL,GOOD,BADTRACE,PLAYER,DONE,BAD=11,1,14,8,9,15,13
DIRS={1:(0,-1),2:(0,1),3:(-1,0),4:(1,0)}
LEVELS=[
 {"name":"One Difference","good":[4,4],"bad":[4,3]},
 {"name":"Shared Prefix","good":[1,4,4],"bad":[1,4,2]},
 {"name":"Middle Error","good":[3,1,4,2],"bad":[3,2,4,2]},
 {"name":"Two Counterexamples","good":[1,1,4,2,4],"bad":[1,1,3,2,4]},
 {"name":"Delayed Distinction","good":[4,1,3,2,4,1],"bad":[4,1,3,2,3,1]},
 {"name":"Negative Demonstration","good":[1,4,2,3,1,4,4],"bad":[1,4,2,3,1,3,4]},
]


class Display(RenderableUserDisplay):
 def __init__(self,game):self.game=game
 @staticmethod
 def mark(frame,a,x,y,c):
  dx,dy=DIRS[a];frame[y-2:y+3,x-2:x+3]=c;frame[y+dy*4-1:y+dy*4+2,x+dx*4-1:x+dx*4+2]=c
 def render_interface(self,frame:np.ndarray)->np.ndarray:
  g=self.game;frame[:,:]=BG;frame[6:25,4:60]=PANEL;frame[29:48,4:60]=PANEL
  for i,a in enumerate(g.good):self.mark(frame,a,9+i*7,15,GOOD)
  for i,a in enumerate(g.bad):self.mark(frame,a,9+i*7,38,BADTRACE)
  for i in range(len(g.good)):frame[53:58,8+i*7:13+i*7]=DONE if i<g.progress else PLAYER
  if g.failed:frame[60:63,25:39]=BAD
  return frame


class Q112(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.good=[];self.bad=[];self.progress=0;self.failed=False
  levels=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS]
  super().__init__("q112",levels,Camera(0,0,64,64,BG,BG,[self.display]),False,len(levels),[1,2,3,4])
 def on_set_level(self,level):
  s=LEVELS[self.level_index];self.good=list(s["good"]);self.bad=list(s["bad"]);self.progress=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a!=self.good[self.progress]:self.failed=True;self.lose()
  else:
   self.progress+=1
   if self.progress==len(self.good):self.next_level()
  self.complete_action()
