"""q769 Monsoon Obligation -- repay an identity-bound debt at sparse cycle alignments."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,SEED,STORM,CYCLEA,CYCLEB,REWARD,BAD=8,2,9,12,10,14,6,15
LEVELS=[
 {"name":"Borrowed Rain","identity":1,"mods":[2,3],"target":[1,2],"rewards":1},
 {"name":"Unequal Cycles","identity":2,"mods":[3,4],"target":[2,1],"rewards":1},
 {"name":"Sparse Phase Pair","identity":1,"mods":[4,5],"target":[3,4],"rewards":2},
 {"name":"Intervening Rewards","identity":2,"mods":[5,6],"target":[1,5],"rewards":2},
 {"name":"Causal Identity","identity":1,"mods":[6,7],"target":[4,2],"rewards":3},
 {"name":"Monsoon Obligation","identity":2,"mods":[7,8],"target":[5,7],"rewards":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=GARDEN;f[15:29,8:22]=SEED;f[15:29,42:56]=SEED;f[33:38,8:8+g.phase[0]*7]=CYCLEA;f[40:45,8:8+g.phase[1]*5]=CYCLEB;f[49:53,8:8+g.collected*12]=REWARD
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q769(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.identity=self.rewards=self.collected=self.stage=0;self.mods=self.target=self.phase=[];self.obligation=None;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q769",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.identity=s["identity"];self.mods=list(s["mods"]);self.target=list(s["target"]);self.rewards=s["rewards"];self.phase=[0,0];self.collected=self.stage=0;self.obligation=None;self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if self.stage==0 and z in (1,2):self.obligation=z;self.stage=1
  elif self.stage==1 and z==3:self.phase[0]=(self.phase[0]+1)%self.mods[0]
  elif self.stage==1 and z==4:self.phase[1]=(self.phase[1]+1)%self.mods[1]
  elif self.stage==1 and z==5:
   if self.phase==self.target:
    self.collected+=1;self.phase=[(p+1)%m for p,m in zip(self.phase,self.mods)]
    if self.collected==self.rewards:self.stage=2
   else:self.failed=True;self.lose()
  elif self.stage==2 and z in (1,2):
   if z==self.obligation==self.identity:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
