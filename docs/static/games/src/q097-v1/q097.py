"""q097 Factory Plan -- infer and schedule an unlabeled production hierarchy."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FLOOR,MACHINE,INPUT,OUTPUT,STOCK,TARGET,CURSOR,BAD=11,1,3,12,9,6,14,10,8
LEVELS=[
 {"name":"One Machine","inv":[1,0],"recipes":[({0:1},1)],"target":1,"plan":[0]},
 {"name":"Two Stage","inv":[1,0,0],"recipes":[({0:1},1),({1:1},2)],"target":2,"plan":[0,1]},
 {"name":"Shared Intermediate","inv":[2,0,0,0],"recipes":[({0:1},1),({1:1},2),({1:1,2:1},3)],"target":3,"plan":[0,1,0,2]},
 {"name":"Converging Lines","inv":[1,1,0,0,0],"recipes":[({0:1},2),({1:1},3),({2:1,3:1},4)],"target":4,"plan":[0,1,2]},
 {"name":"Reusable Part","inv":[3,0,0,0,0,0],"recipes":[({0:1},1),({1:2},2),({1:1},3),({2:1,3:1},5)],"target":5,"plan":[0,0,1,0,2,3]},
 {"name":"Factory Plan","inv":[2,1,0,0,0,0,0],"recipes":[({0:1},2),({1:1},3),({2:1,3:1},4),({0:1},5),({4:1,5:1},6)],"target":6,"plan":[0,1,2,3,4]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=FLOOR
  for i,(need,out) in enumerate(g.recipes):
   x=7+i*10;f[15:34,x:x+8]=MACHINE;f[18:22,x+1:x+min(7,len(need)*2+2)]=INPUT;f[27:31,x+2:x+6]=OUTPUT;f[10:13,x:x+8]=CURSOR if i==g.cursor else FLOOR
  for i,v in enumerate(g.inv):x=7+i*8;f[42:50,x:x+6]=STOCK if v else FLOOR;f[45-v*2:48,x+1:x+5]=OUTPUT if v else FLOOR
  f[52:55,7:7+g.target*7]=TARGET
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q097(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.inv=[];self.recipes=[];self.target=self.cursor=0;self.budget=28;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q097",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.inv=list(s["inv"]);self.recipes=[(dict(n),o) for n,o in s["recipes"]];self.target=s["target"];self.cursor=0;self.budget=28;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a==3:self.cursor=(self.cursor-1)%len(self.recipes)
  elif a==4:self.cursor=(self.cursor+1)%len(self.recipes)
  elif a==5:
   need,out=self.recipes[self.cursor]
   if all(self.inv[k]>=v for k,v in need.items()):
    for k,v in need.items():self.inv[k]-=v
    self.inv[out]+=1
   else:self.failed=True;self.lose()
  elif a==6:
   if self.inv[self.target]>0:self.next_level()
   else:self.failed=True;self.lose()
  if self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
