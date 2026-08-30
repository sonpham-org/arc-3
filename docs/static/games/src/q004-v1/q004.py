"""q004 Witness Queue -- junctions commit while watched and travel only while unseen."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,PATH,WATCH,DARK,TOKEN,GOAL,BAD=10,1,3,11,4,6,14,8
LEVELS=[{"name":n,"route":r} for n,r in [("One Junction",[0]),("Turn Away",[1,0]),("Alternation",[2,1,3]),("Long Queue",[3,0,2,1]),("Witness Chain",[1,3,2,0,1]),("Witness Queue",[2,0,3,1,2,0])]]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,5:59]=FIELD
  for i,d in enumerate(g.route):
   x=10+i*8;f[27:36,x:x+6]=PATH;dx,dy=((0,-1),(1,0),(0,1),(-1,0))[d];f[28+dy*3:32+dy*3,x+1+dx*2:x+5+dx*2]=GOAL if i>=g.progress else DARK
  x=10+min(g.progress,len(g.route)-1)*8;f[39:46,x:x+6]=TOKEN
  f[2:6,8:56]=WATCH if g.watched else DARK;f[59:63,25:39]=BAD if g.failed else g.selector+6
  return f
class Q004(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.route=[];self.progress=self.selector=0;self.watched=False;self.phase=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q004",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,3,4,5,6])
 def on_set_level(self,l):self.route=list(LEVELS[self.level_index]["route"]);self.progress=self.selector=self.phase=0;self.watched=False;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.selector=(self.selector-1)%4
  elif a==4:self.selector=(self.selector+1)%4
  elif a==5:self.watched=not self.watched
  elif a==6 and self.phase==0 and self.watched and self.selector==self.route[self.progress]:self.phase=1
  elif a==1 and self.phase==1 and not self.watched:
   self.progress+=1;self.phase=0
   if self.progress==len(self.route):self.next_level()
  else:self.failed=True;self.lose()
  self.complete_action()
