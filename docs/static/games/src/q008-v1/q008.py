"""q008 Veiled Orchestra -- occluded mechanisms advance while visible ones hold phase."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,MECH,PHASE,TARGET,VEIL,CURSOR,BAD=2,7,10,12,14,6,11,8
LEVELS=[
 {"name":"One Hidden Beat","mod":3,"start":[0,0],"target":[1,2]},
 {"name":"Selective Pulse","mod":4,"start":[1,0],"target":[3,1]},
 {"name":"Phase Pair","mod":5,"start":[0,2,1],"target":[4,1,3]},
 {"name":"Occluded Counterpoint","mod":5,"start":[1,3,0],"target":[4,0,2]},
 {"name":"Four Sections","mod":6,"start":[0,1,2,3],"target":[5,3,1,4]},
 {"name":"Veiled Orchestra","mod":7,"start":[1,4,0,2],"target":[6,2,3,0]}]
class Display(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f:np.ndarray)->np.ndarray:
  g=self.g;f[:,:]=BG;f[7:57,4:60]=STAGE;n=len(g.phases)
  for i,(p,t) in enumerate(zip(g.phases,g.target)):
   x=8+i*(48//n);f[17:39,x:x+9]=MECH;f[35-p*3:38,x+2:x+7]=PHASE;f[12:15,x:x+min(9,t+2)]=TARGET
   if g.hidden[i]:f[16:40,x-1:x+10]=VEIL;f[19:37,x+1:x+8]=MECH
   f[44:48,x:x+9]=CURSOR if i==g.cursor else STAGE
  if g.failed:f[60:63,25:39]=BAD
  return f
class Q008(ARCBaseGame):
 def __init__(self):
  self.display=Display(self);self.phases=self.target=[];self.hidden=[];self.mod=self.cursor=0;self.budget=48;self.failed=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(s),name=s["name"]) for s in LEVELS];super().__init__("q008",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,len(ls),[1,2,3,5,6])
 def on_set_level(self,l):
  s=LEVELS[self.level_index];self.phases=list(s["start"]);self.target=list(s["target"]);self.mod=s["mod"];self.hidden=[False]*len(self.phases);self.cursor=0;self.budget=48;self.failed=False
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  self.budget-=1
  if a==1:self.cursor=(self.cursor-1)%len(self.phases)
  elif a==2:self.cursor=(self.cursor+1)%len(self.phases)
  elif a==3:self.hidden[self.cursor]=not self.hidden[self.cursor]
  elif a==5:self.phases=[(p+1)%self.mod if h else p for p,h in zip(self.phases,self.hidden)]
  elif a==6:
   if self.phases==self.target:self.next_level()
   else:self.failed=True;self.lose()
  else:self.failed=True;self.lose()
  if self.budget<=0:self.failed=True;self.lose()
  self.complete_action()
