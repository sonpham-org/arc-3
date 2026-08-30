"""q215 Waystation Veil -- schedule attention while hidden corridors and an adaptive rival evolve."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,DESERT,DUNE,WALKER,FOCUS,RIVAL,GOAL,BAD=0,13,11,15,10,12,14,8
LEVELS=[
 {"name":"First Veil","plan":(1,4,2)},{"name":"Counter Camp","plan":(2,4,5,1)},
 {"name":"Hidden Crossing","plan":(3,5,2,4,1)},{"name":"Coupled Dunes","plan":(1,4,1,4,3,5)},
 {"name":"Rival Memory","plan":(2,5,2,4,3,4,1)},{"name":"Waystation Veil","plan":(3,4,5,1,5,2,4,3)}]
def advance(state,a):
 regions,focus,last,rival=state;regions=list(regions)
 if a in (1,2,3):
  focus=a-1
  for i in range(3):
   if i!=focus:regions[i]=(regions[i]+i+1+len(last))%4
 else:
  p=a-4;rival=(1-p) if len(last)>=1 and last[-1]==p else p;regions[rival]=(regions[rival]+1+rival)%4;last=(last+(p,))[-2:]
 return tuple(regions),focus,last,rival
def target(x):
 s=((0,1,2),0,(),0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=DESERT
  for i,v in enumerate(g.regions):
   x=8+i*18;f[10:39,x:x+14]=DUNE;f[32-v*5:37,x+3:x+11]=WALKER
   if i==g.focus:f[7:10,x:x+14]=FOCUS
  f[44:50,8+g.rival*18:22+g.rival*18]=RIVAL
  for i,v in enumerate(g.last):f[53+i*4:56+i*4,8:8+(v+1)*18]=GOAL
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q215(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.regions=(0,1,2);self.focus=0;self.last=();self.rival=0;self.target=target(LEVELS[0]);self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q215",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.regions=(0,1,2);self.focus=0;self.last=();self.rival=0;self.target=target(LEVELS[self.level_index]);self.bad=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.regions,self.focus,self.last,self.rival=advance((self.regions,self.focus,self.last,self.rival),a)
  elif a==6:
   if (self.regions,self.focus,self.last,self.rival)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
