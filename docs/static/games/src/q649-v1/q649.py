"""q649 Monsoon Sandbox -- preserve counterfactual evidence while resetting unequal weather cycles."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,RAIN,CELL,EVIDENCE,CYCLE,POLICY,BAD=4,14,12,15,10,11,9,8
LEVELS=[
 {"name":"First Forecast","steps":1,"policy":0},{"name":"Unequal Cycles","steps":2,"policy":1},
 {"name":"Phase Pair","steps":3,"policy":2},{"name":"Counterfactual Storm","steps":5,"policy":1},
 {"name":"Delayed Cell","steps":7,"policy":2},{"name":"Monsoon Sandbox","steps":11,"policy":0}]
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=GARDEN;f[11:25,9:25]=RAIN if g.evidence&1 else CELL;f[11:25,39:55]=RAIN if g.evidence&2 else CELL
  f[32:36,8:8+g.p2*18]=CYCLE;f[39:43,8:8+g.p3*13]=CYCLE;f[47:51,8:8+g.evidence*10]=EVIDENCE;f[54:58,8:8+g.policy*14]=POLICY
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q649(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.p2=self.p3=self.evidence=self.policy=0;self.reset_done=False;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q649",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.p2=self.p3=self.evidence=self.policy=0;self.reset_done=False;self.bad=False
 def tick(self,n=1):self.p2=(self.p2+n)%2;self.p3=(self.p3+n)%3
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a==1:self.evidence|=1;self.tick(1)
  elif a==2:self.evidence|=2;self.tick(2)
  elif a==3:self.tick(1)
  elif a==4:self.p2=self.p3=0;self.reset_done=True
  elif a==5:self.policy=(self.policy+1)%3
  elif a==6:
   if self.evidence==3 and self.reset_done and (self.p2,self.p3)==(x["steps"]%2,x["steps"]%3) and self.policy==x["policy"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
