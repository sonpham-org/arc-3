"""q571 Tapestry Counter -- shape a rival whose pattern completion rewires the loom."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,LOOM,SHUTTLE,THREAD,REWIRE,RIVAL,HISTORY,GOAL,BAD=2,10,14,9,6,12,11,13,15
LEVELS=[{"name":"First Tactic","seq":(1,)},{"name":"Second Treatment","seq":(2,1)},{"name":"Pattern Response","seq":(3,1,2)},{"name":"Rewired Counter","seq":(1,4,2,3)},{"name":"Shape The Loom","seq":(2,3,1,4,2,1)},{"name":"Tapestry Counter","seq":(3,1,2,4,1,3,2,1,4)}]
def advance(s,a):
 recent,rival,shuttle,graph,pattern,exploit=s
 if a in (1,2):recent=(recent+(a,))[-2:];shuttle=(shuttle+a+rival)%8;pattern=(pattern+shuttle)%5;rival=(sum(recent)+pattern+graph)%3
 elif a==3:graph=(graph+1+int(pattern>=2))%4;pattern=0
 elif a==4:shuttle=(shuttle+2+graph)%8;rival=(rival+graph)%3
 elif a==5:exploit=(recent,rival,shuttle,graph,pattern)
 return recent,rival,shuttle,graph,pattern,exploit
for x in LEVELS:
 s=((),0,0,0,0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LOOM
  for i in range(8):x=8+(i%4)*12;y=8+(i//4)*13;f[y:y+9,x:x+9]=THREAD;f[y+2:y+7,x+2:x+7]=SHUTTLE if i==g.shuttle else REWIRE
  for i,a in enumerate(g.recent):f[38:44,9+i*20:23+i*20]=HISTORY;f[40:42,12+i*20:12+i*20+a*4]=THREAD
  f[49:53,8:8+g.rival*16+8]=RIVAL;f[55:59,8:8+g.graph*11+7]=REWIRE
  if g.exploit:f[52:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q571(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q571",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.rival=self.shuttle=self.graph=self.pattern=0;self.exploit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.recent,self.rival,self.shuttle,self.graph,self.pattern,self.exploit=advance((self.recent,self.rival,self.shuttle,self.graph,self.pattern,self.exploit),a)
  elif a==6:
   if (self.recent,self.rival,self.shuttle,self.graph,self.pattern,self.exploit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
