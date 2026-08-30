"""q313 Impeller Ledger -- conserve rotor stock and pay for redundant state samples."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CHAMBER,ROTOR,RIDER,STOCK,SAMPLE,WAKE,COST,BAD=11,3,4,9,14,10,15,12,8
LEVELS=[
 {"name":"First Transfer","plan":(1,4),"budget":2},
 {"name":"Counter Wake","plan":(2,5,4),"budget":3},
 {"name":"Global Stock","plan":(3,1,4,2),"budget":4},
 {"name":"Useful Sample","plan":(2,4,5,3,4),"budget":5},
 {"name":"Redundancy Price","plan":(1,4,1,5,4,3),"budget":6},
 {"name":"Impeller Ledger","plan":(3,2,4,5,1,4,2,3),"budget":8}]
def advance(s,a):
 stock,wake,samples,cost=s;stock=list(stock);samples=list(samples)
 if a in (1,2,3):
  src=a-1;dst=a%3
  if stock[src]:stock[src]-=1;stock[dst]+=1
 elif a==4:
  item=(tuple(stock),wake);cost+=2 if item in samples else 1;samples.append(item)
 elif a==5:stock.reverse();wake=(wake+1)%4
 return tuple(stock),wake,tuple(samples),cost
def target(x):
 s=((4,3,2),0,(),0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CHAMBER
  for i,v in enumerate(g.stock):x=8+i*18;f[10:35,x:x+14]=ROTOR;f[15+i*5:22+i*5,x+4:x+10]=RIDER;f[39:42,x:x+v*3]=STOCK
  f[46:49,8:8+len(g.samples)*7]=SAMPLE;f[51:54,8:8+g.wake*12]=WAKE;f[56:59,8:8+g.cost*6]=COST
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q313(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self.target=target(LEVELS[0]);self._reset()
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q313",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(4,3,2);self.wake=0;self.samples=();self.cost=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   self.stock,self.wake,self.samples,self.cost=advance((self.stock,self.wake,self.samples,self.cost),a)
   if self.cost>x["budget"]:self.bad=True;self.lose()
  elif a==6:
   if (self.stock,self.wake,self.samples,self.cost)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
