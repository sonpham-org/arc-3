"""q054 Gear Teeth -- allocate finite teeth to synchronize transmission ratios."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,GEAR,TOOTH,TARGET,CURSOR,BAD=12,1,10,9,14,11,8
LEVELS=[
 {"name":"Add One Tooth","start":[2,2],"target":[3,2],"bank":1}, {"name":"Equal Wheels","start":[2,3],"target":[4,4],"bank":3},
 {"name":"Three Gear Train","start":[2,2,3],"target":[3,4,3],"bank":3}, {"name":"Ratio Pair","start":[2,3,2],"target":[4,3,5],"bank":5},
 {"name":"Distant Sync","start":[2,2,3,2],"target":[3,5,3,4],"bank":6}, {"name":"Gear Teeth","start":[2,3,2,4],"target":[5,4,6,4],"bank":8}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=SHOP;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):
   x=11+i*(44//n);f[22:36,x-5:x+6]=GEAR;f[27:31,x-2:x+3]=SHOP
   for j in range(v):f[18+(j%2)*22:21+(j%2)*22,x-5+j:x-3+j]=TOOTH
   f[12:15,x-5:x-5+t*2]=TARGET
  f[42:47,6+g.cursor*(44//n):15+g.cursor*(44//n)]=CURSOR;f[50:54,7:7+g.bank*5]=TOOTH
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q054(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=[];self.bank=self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q054",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=list(s["start"]);self.target=list(s["target"]);self.bank=s["bank"];self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.values)
  elif a==4:self.cursor=(self.cursor+1)%len(self.values)
  elif a==5 and self.bank:self.values[self.cursor]+=1;self.bank-=1
  elif a==6:
   if self.values==self.target and self.bank==0:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
