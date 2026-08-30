"""q295 Alloy Ledger -- route a conserved quantity in a rotating local frame."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FOUNDRY,BILLET,FORCE,FRAME,CURSOR,TARGET,BAD=1,7,12,14,15,10,6,8
LEVELS=[
 {"name":"Conserved Billets","start":[3,0,0],"target":[0,3,0]},
 {"name":"Alternating Lane","start":[1,3,0],"target":[2,0,2]},
 {"name":"Rotating Frame","start":[0,2,3],"target":[3,1,1]},
 {"name":"Global Ledger","start":[4,0,2],"target":[1,3,2]},
 {"name":"Local Appearance","start":[2,3,2],"target":[5,1,1]},
 {"name":"Alloy Ledger","start":[0,4,4],"target":[3,2,3]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[5:59,4:60]=FOUNDRY
  for i,v in enumerate(g.amounts):x=8+i*18;f[15:47,x:x+12]=FORCE;f[47-v*4:47,x:x+12]=BILLET
  f[50:55,8+g.cursor*18:20+g.cursor*18]=CURSOR;f[8:11,8:8+g.frame*13]=FRAME
  if g.bad:f[61:64,22:42]=BAD
  return f
class Q295(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.amounts=[];self.cursor=self.frame=0;self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q295",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,6])
 def on_set_level(self,l):self.amounts=list(LEVELS[self.level_index]["start"]);self.cursor=self.frame=0;self.bad=False
 def step(self):
  z=self.action.id.value
  if z==0:self.complete_action();return
  i=(self.cursor+self.frame)%3;j=(i+1)%3
  if z==1 and self.amounts[i]:self.amounts[i]-=1;self.amounts[j]+=1
  elif z==2 and self.amounts[j]:self.amounts[j]-=1;self.amounts[i]+=1
  elif z==3:self.frame=(self.frame+1)%3
  elif z==4:self.cursor=(self.cursor+1)%3
  elif z==6:
   if self.amounts==LEVELS[self.level_index]["target"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
