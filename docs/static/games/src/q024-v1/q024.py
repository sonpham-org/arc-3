"""q024 Last Probe -- design finite experiments before one irreversible commitment."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LAB,HYP,PROBE,YES,NO,CURSOR,BAD=13,0,1,10,14,8,11,5
LEVELS=[
 {"name":"One Probe","target":1,"probes":[[0,1]],"required":[0]},
 {"name":"Choose Experiment","target":2,"probes":[[0,1],[2,3]],"required":[1]},
 {"name":"Two Bits","target":3,"probes":[[0,1],[0,2]],"required":[0,1]},
 {"name":"Sparse Bank","target":0,"probes":[[0,3],[1,2],[2,3]],"required":[0,1]},
 {"name":"Final Evidence","target":2,"probes":[[0,1],[1,2],[2,3]],"required":[1,2]},
 {"name":"Last Probe","target":3,"probes":[[0,1],[0,2],[1,3]],"required":[0,1,2]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[8:56,4:60]=LAB
  for i in range(4):x=9+i*13;f[15:27,x:x+9]=HYP;f[11:14,x:x+9]=CURSOR if i==g.hyp else LAB
  for i,p in enumerate(g.probes):x=10+i*14;f[38:45,x:x+10]=PROBE;f[47:52,x:x+10]=YES if i in g.results and g.results[i] else NO if i in g.results else LAB;f[34:37,x:x+10]=CURSOR if i==g.cursor else LAB
  if g.failed:f[59:63,25:39]=BAD
  return f
class Q024(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.target=self.hyp=self.cursor=0;self.probes=[];self.required=set();self.results={};self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q024",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,4,5,6])
 def on_set_level(self,l):s=LEVELS[self.level_index];self.target=s["target"];self.probes=[set(x) for x in s["probes"]];self.required=set(s["required"]);self.hyp=self.cursor=0;self.results={};self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a==1:self.hyp=(self.hyp-1)%4
  elif a==2:self.hyp=(self.hyp+1)%4
  elif a==3:self.cursor=(self.cursor-1)%len(self.probes)
  elif a==4:self.cursor=(self.cursor+1)%len(self.probes)
  elif a==5:self.results[self.cursor]=self.target in self.probes[self.cursor]
  elif a==6:
   if self.hyp==self.target and self.required<=self.results.keys():self.next_level()
   else:self.failed=True;self.lose()
  self.complete_action()
