"""q036 Loop Current -- redistribute circulation while preserving the loop sum."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHANNEL,LOOP,CURRENT,TARGET,CURSOR,BAD=10,1,3,9,14,12,8
LEVELS=[
 {"name":"Split Flow","start":[3,0],"target":[2,1],"ops":[(0,1)]}, {"name":"Closed Loop","start":[4,0,0],"target":[2,1,1],"ops":[(0,1),(0,2)]},
 {"name":"Invisible Return","start":[3,2,0],"target":[1,2,2],"ops":[(0,1),(1,2),(0,2)]}, {"name":"Loop Sum","start":[5,0,1],"target":[2,2,2],"ops":[(0,1),(1,2),(0,2)]},
 {"name":"Coupled Circuits","start":[4,2,0,0],"target":[1,2,2,1],"ops":[(0,1),(1,2),(2,3),(0,3)]}, {"name":"Loop Current","start":[5,1,0,0],"target":[1,1,2,2],"ops":[(0,1),(1,2),(2,3),(0,3),(0,2)]}]
def flow(vals,op):
 a,b=op;o=list(vals)
 if o[a]:o[a]-=1;o[b]+=1
 return tuple(o)
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:56,4:60]=CHANNEL;n=len(g.values)
  for i,(v,t) in enumerate(zip(g.values,g.target)):x=9+i*(47//n);f[18:40,x:x+10]=LOOP;f[34-v*4:38,x+2:x+8]=CURRENT;f[13:16,x:x+t*3]=TARGET
  for i in range(len(g.ops)):f[45:49,6+i*9:13+i*9]=CURSOR if i==g.cursor else LOOP
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q036(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.values=self.target=();self.ops=[];self.cursor=0;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q036",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.values=tuple(s["start"]);self.target=tuple(s["target"]);self.ops=list(map(tuple,s["ops"]));self.cursor=0;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==3:self.cursor=(self.cursor-1)%len(self.ops)
  elif a==4:self.cursor=(self.cursor+1)%len(self.ops)
  elif a==5:self.values=flow(self.values,self.ops[self.cursor])
  elif a==6:
   if self.values==self.target:self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
