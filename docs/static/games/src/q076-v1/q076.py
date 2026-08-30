"""q076 Rule Thermostat -- heat and cool the board to select its causal regime."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,COLD,WARM,HOT,STATE,TARGET,BAD=11,0,10,12,8,9,14,13
LEVELS=[
 {"name":"Warm Rule","start":0,"target":3,"mod":6}, {"name":"Cool First","start":4,"target":1,"mod":7},
 {"name":"Three Regimes","start":1,"target":6,"mod":8}, {"name":"Thermal Plan","start":5,"target":2,"mod":9},
 {"name":"Rule Control","start":2,"target":8,"mod":10}, {"name":"Rule Thermostat","start":7,"target":3,"mod":11}]
def apply(value,temp,a,mod):
 delta=(1,2,3)[temp] if a==3 else (-1,-2,-3)[temp]
 return (value+delta)%mod
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:55,4:60]=LAB;f[14:24,8:18]=COLD;f[14:24,27:37]=WARM;f[14:24,46:56]=HOT;f[30:40,8:8+g.value*4]=STATE;f[44:49,8:8+g.target*4]=TARGET;f[3:6,9+g.temp*19:17+g.temp*19]=STATE
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q076(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.value=self.target=self.mod=0;self.temp=1;self.budget=20;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q076",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.value=s["start"];self.target=s["target"];self.mod=s["mod"];self.temp=1;self.budget=20;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a==1:self.temp=min(2,self.temp+1)
  elif a==2:self.temp=max(0,self.temp-1)
  elif a in (3,4):self.value=apply(self.value,self.temp,a,self.mod)
  elif a==6:
   if self.value==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
