"""q034 Area Keeper -- transformations alter silhouette while conserving filled area."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STUDIO,SHAPE,SOCKET,TOOL,CURSOR,DONE,BAD=10,1,6,14,12,11,9,8
LEVELS=[
 {"name":"Same Area","areas":[4,6],"target":4,"turns":1}, {"name":"Stretch Test","areas":[3,6,8],"target":6,"turns":2},
 {"name":"Folded Shapes","areas":[5,8,6],"target":8,"turns":2}, {"name":"Shear Gallery","areas":[6,9,4,8],"target":9,"turns":3},
 {"name":"Silhouette Trap","areas":[7,10,8,9],"target":10,"turns":3}, {"name":"Area Keeper","areas":[8,12,9,10,6],"target":12,"turns":4}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=STUDIO
  for i,a in enumerate(g.areas):
   x=7+i*10;w=1+(g.forms[i]%4);h=max(1,(a+w-1)//w);f[32-h*3:32,x:x+min(8,w*2)]=SHAPE;f[36:40,x:x+8]=CURSOR if i==g.cursor else STUDIO
  f[11:15,9:9+g.target*3]=SOCKET;f[46:51,8:8+g.turns*8]=TOOL
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q034(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.areas=[];self.target=self.turns=self.cursor=0;self.forms=[];self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q034",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.areas=list(s["areas"]);self.target=s["target"];self.turns=s["turns"];self.cursor=0;self.forms=[0]*len(self.areas);self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.areas)
  elif a==4:self.cursor=(self.cursor+1)%len(self.areas)
  elif a==5 and self.turns:self.forms[self.cursor]=(self.forms[self.cursor]+1)%4;self.turns-=1
  elif a==6:
   if self.areas[self.cursor]==self.target and self.turns==0:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  self.complete_action()
