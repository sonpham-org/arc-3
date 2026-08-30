"""q055 Funnel Forge -- assemble short wall segments into a particle-sorting funnel."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FORGE,SEGMENT,BUILT,PARTICLE,TARGET,CURSOR,BAD=12,1,3,10,9,14,11,8
LEVELS=[
 {"name":"First Wall","segments":2,"need":[0]}, {"name":"Narrow Funnel","segments":3,"need":[0,2]},
 {"name":"Size Split","segments":4,"need":[1,2]}, {"name":"Momentum Chute","segments":5,"need":[0,2,4]},
 {"name":"Two Exits","segments":6,"need":[1,2,4,5]}, {"name":"Funnel Forge","segments":7,"need":[0,2,3,5,6]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=FORGE
  for i in range(g.segments):x=7+i*7;f[16+i%2*8:20+i%2*8,x:x+6]=BUILT if i in g.built else SEGMENT;f[12:15,x:x+6]=CURSOR if i==g.cursor else FORGE
  f[35:40,12:20]=PARTICLE;f[43:48,40:52]=TARGET
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q055(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.segments=self.cursor=0;self.need=self.built=set();self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q055",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.segments=s["segments"];self.need=set(s["need"]);self.built=set();self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%self.segments
  elif a==4:self.cursor=(self.cursor+1)%self.segments
  elif a==5:self.built.symmetric_difference_update({self.cursor})
  elif a==6:
   if self.built==self.need:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
