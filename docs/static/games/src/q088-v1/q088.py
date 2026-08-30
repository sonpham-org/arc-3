"""q088 Mask Debt -- masks transfer capabilities, but obligations stay with identities."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,COURT,IDA,IDB,MASK,DEBT,TASK,DONE,BAD=11,7,9,12,15,8,10,14,6
LEVELS=[
 {"name":"Debt Stays","tasks":[0,1]}, {"name":"Return the Mask","tasks":[1,0,1]},
 {"name":"Two Wearers","tasks":[0,1,1,0]}, {"name":"Accumulated Promise","tasks":[1,1,0,1,0]},
 {"name":"Pass Without Debt","tasks":[0,1,0,0,1,1]}, {"name":"Mask Debt","tasks":[1,0,1,1,0,0,1]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=COURT
  for i in range(2):
   x=14+i*30;f[20:38,x:x+12]=IDA if i==0 else IDB;f[15:19,x:x+12]=MASK if g.owner==i else COURT;f[41:45,x:x+g.debt[i]*5]=DEBT;f[48:51,x:x+12]=DONE if g.selected==i else COURT
  for i,t in enumerate(g.tasks):x=7+i*7;f[4:7,x:x+5]=DONE if i<g.progress else TASK+(t%2)
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q088(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.tasks=[];self.progress=self.owner=self.selected=0;self.debt=[0,0];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q088",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):self.tasks=list(LEVELS[self.level_index]["tasks"]);self.progress=self.owner=self.selected=0;self.debt=[0,0];self.failed=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  if z==1:self.selected=0
  elif z==2:self.selected=1
  elif z==3:self.owner=1-self.owner
  elif z==4:
   if self.progress<len(self.tasks) and self.owner==self.tasks[self.progress]:self.debt[self.owner]+=1;self.progress+=1
   else:self.failed=True;self.lose()
  elif z==5:
   if self.debt[self.selected]:self.debt[self.selected]-=1
  elif z==6:
   if self.progress==len(self.tasks) and self.debt==[0,0]:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
