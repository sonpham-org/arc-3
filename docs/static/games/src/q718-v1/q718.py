"""q718 Breakwater Gradient -- conserved quantities with a dormant phase intervention."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,WATER,CAPACITY,PHASE,CURSOR,SEAL,BAD=8,10,12,14,15,13,2,3
LEVELS=[
 {"name":"Conserved Tide","start":[3,0,0],"target":[0,3,0],"mod":3,"phase":1,"intervene":False},
 {"name":"Capacity Locks","start":[1,3,0],"target":[2,0,2],"mod":4,"phase":3,"intervene":True},
 {"name":"Dormant Sluice","start":[0,2,3],"target":[3,1,1],"mod":5,"phase":2,"intervene":True},
 {"name":"Two Subgoals","start":[4,0,2],"target":[1,3,2],"mod":4,"phase":1,"intervene":False},
 {"name":"Early Intervention","start":[2,3,2],"target":[5,1,1],"mod":5,"phase":4,"intervene":True},
 {"name":"Breakwater Gradient","start":[0,4,4],"target":[3,2,3],"mod":6,"phase":5,"intervene":False}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,4:60]=HARBOR
  for i,v in enumerate(g.amounts):x=8+i*18;f[16:48,x:x+12]=CAPACITY;f[48-v*4:48,x:x+12]=WATER
  f[51:56,8+g.cursor*18:20+g.cursor*18]=CURSOR;f[8:11,8:8+g.phase*7]=PHASE
  if g.sealed:f[8:13,50:56]=SEAL
  if g.bad:f[60:63,20:44]=BAD
  return f
class Q718(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.amounts=[];self.cursor=self.phase=self.moves=0;self.sealed=self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q718",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.amounts=list(LEVELS[self.level_index]["start"]);self.cursor=self.phase=self.moves=0;self.sealed=self.bad=False
 def fail(self):self.bad=True;self.lose()
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  l=LEVELS[self.level_index];n=(self.cursor+1)%3
  if z==1 and self.amounts[self.cursor]>0:self.amounts[self.cursor]-=1;self.amounts[n]+=1;self.moves+=1
  elif z==2 and self.amounts[n]>0:self.amounts[n]-=1;self.amounts[self.cursor]+=1;self.moves+=1
  elif z==3:self.cursor=n;self.moves+=1
  elif z==4:self.phase=(self.phase+1)%l["mod"];self.moves+=1
  elif z==5 and self.moves==0 and not self.sealed:self.sealed=True
  elif z==6:
   effective=(self.phase+(1 if self.sealed else 0))%l["mod"]
   if self.amounts==l["target"] and effective==l["phase"] and self.sealed==l["intervene"]:self.next_level()
   else:self.fail()
  else:self.fail()
  self.complete_action()
