"""q044 Memory Camera -- preserve only the regions needed after the scene vanishes."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SCENE,REGION,SAVED,HIDDEN,QUERY,CURSOR,BAD=4,1,9,14,3,12,11,8
LEVELS=[
 {"name":"One Snapshot","regions":[1,2,3],"need":[1],"bank":1}, {"name":"Choose Memory","regions":[3,1,4,2],"need":[0,3],"bank":2},
 {"name":"Later Query","regions":[2,4,1,3],"need":[2,0],"bank":2}, {"name":"Tiny Bank","regions":[4,2,3,1,2],"need":[3,1],"bank":2},
 {"name":"Ordered Recall","regions":[1,3,2,4,1,2],"need":[4,1,5],"bank":3}, {"name":"Memory Camera","regions":[4,1,3,2,4,2,1],"need":[6,2,4],"bank":3}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=SCENE
  if not g.closed:
   for i,v in enumerate(g.regions):x=7+i*7;f[17:27,x:x+5]=REGION;f[19:24,x:x+v]=SAVED if i in g.saved else REGION
  else:f[14:31,7:57]=HIDDEN
  for j,i in enumerate(g.need):x=9+j*13;f[40:48,x:x+8]=QUERY if j>=g.recall else SAVED
  f[3:6,7+g.cursor*7:12+g.cursor*7]=CURSOR
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q044(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.regions=self.need=[];self.bank=self.cursor=self.recall=0;self.saved=[];self.closed=False;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q044",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.regions=list(s["regions"]);self.need=list(s["need"]);self.bank=s["bank"];self.cursor=self.recall=0;self.saved=[];self.closed=False;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  n=len(self.regions) if not self.closed else len(self.saved)
  if a==3 and n:self.cursor=(self.cursor-1)%n
  elif a==4 and n:self.cursor=(self.cursor+1)%n
  elif a==5 and not self.closed and len(self.saved)<self.bank and self.cursor not in self.saved:self.saved.append(self.cursor)
  elif a==6 and not self.closed:self.closed=True;self.cursor=0
  elif a==6 and self.closed and self.saved:
   if self.saved[self.cursor]==self.need[self.recall]:
    self.recall+=1
    if self.recall==len(self.need):self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
