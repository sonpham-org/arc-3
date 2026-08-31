"""q570 Spore Counter -- shape a rival while two treatment clocks align sparsely."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GREENHOUSE,GLASS,SPORE,RIVAL,CLOCK,SHAPE,CLAIM,BAD=3,8,12,6,2,9,4,13,15
LEVELS=[{"name":"One Alignment","cycles":(2,2),"rounds":1},{"name":"Unequal Alignment","cycles":(2,3),"rounds":1},{"name":"Shape Twice","cycles":(3,3),"rounds":2},{"name":"Sparse Rival","cycles":(3,4),"rounds":2},{"name":"Long Counter","cycles":(4,5),"rounds":3},{"name":"Spore Counter","cycles":(5,6),"rounds":4}]
for x in LEVELS:x["plan"]=((1,)*x["cycles"][0]+(2,)*x["cycles"][1])*x["rounds"]+(5,);x["need"]=2*x["rounds"]-1
def advance(s,a,x):
 history,rival,clocks,shaped,claimed=s;history=list(history);clocks=list(clocks)
 if a in (1,2,3):
  t=a-1
  if history and history[-1]!=t:shaped+=1
  history=(history+[t])[-3:];rival=(sum(history)+len(history))%3
  if a==1:clocks[0]=(clocks[0]+1)%x["cycles"][0]
  elif a==2:clocks[1]=(clocks[1]+1)%x["cycles"][1]
  else:clocks=[(clocks[i]+1)%x["cycles"][i] for i in range(2)]
 elif a==4:clocks=[(clocks[i]+1)%x["cycles"][i] for i in range(2)]
 elif a==5:
  if tuple(clocks)!=(0,0) or shaped<x["need"]:return None
  claimed=(tuple(history),rival,tuple(clocks),shaped)
 return tuple(history),rival,tuple(clocks),shaped,claimed
def target(x):
 s=((),0,(0,0),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GREENHOUSE
  for i in range(3):x=8+i*17;f[8:34,x:x+13]=GLASS+i
  for i,t in enumerate(g.history):f[27-i*6:32-i*6,10+t*17:19+t*17]=SPORE+t
  f[39:43,8:12+g.rival*13]=RIVAL;f[46:49,8:8+g.clocks[0]*8]=CLOCK;f[51:54,8:8+g.clocks[1]*7]=CLOCK+2
  f[56:59,8:8+g.shaped*4]=SHAPE
  if g.claimed:f[38:58,56:59]=CLAIM
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q570(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q570",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.history=();self.rival=0;self.clocks=(0,0);self.shaped=0;self.claimed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.history,self.rival,self.clocks,self.shaped,self.claimed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.history,self.rival,self.clocks,self.shaped,self.claimed=s
  elif a==6:
   if (self.history,self.rival,self.clocks,self.shaped,self.claimed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
