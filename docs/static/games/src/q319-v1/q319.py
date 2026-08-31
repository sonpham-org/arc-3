"""q319 Monsoon Ledger -- conserve rain stock across two unequal storm cycles."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,GARDEN,CLOUD,RAIN,STOCK,CYCLEA,CYCLEB,SEAL,BAD=3,10,9,14,6,11,4,7,15
def routine(n):return tuple((i%4)+1 for i in range(n))+(5,)
LEVELS=[{"name":"Paired Transfer","periods":(2,2),"plan":routine(2)},{"name":"Triple Basin","periods":(3,3),"plan":routine(3)},{"name":"Nested Ledger","periods":(2,4),"plan":routine(4)},{"name":"Unequal Reservoirs","periods":(2,3),"plan":routine(6)},{"name":"Long Balance","periods":(3,4),"plan":routine(12)},{"name":"Monsoon Ledger","periods":(4,5),"plan":routine(20)}]
def advance(s,a,x):
 stock,pa,pb,turns,sealed=s;stock=list(stock)
 if a in (1,2,3,4):
  if a in (1,2,3):
   src=a-1;dst=(src+1+pa+pb)%3
   if stock[src]:stock[src]-=1;stock[dst]+=1
  else:stock=stock[1:]+stock[:1]
  turns+=1;pa=(pa+1)%x["periods"][0];pb=(pb+1)%x["periods"][1]
 elif a==5:
  if pa or pb or turns==0:return None
  sealed=(tuple(stock),sum(stock),turns)
 return tuple(stock),pa,pb,turns,sealed
def target(x):
 s=((4,3,2),0,0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=GARDEN
  for i,v in enumerate(g.stock):x=8+i*18;f[8:33,x:x+14]=CLOUD;f[12:26,x+4:x+10]=RAIN-i;f[36:39,x:x+v*3]=STOCK
  f[44:47,8:11+g.pa*9]=CYCLEA;f[50:53,8:11+g.pb*9]=CYCLEB;f[55:58,44:56]=SEAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q319(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q319",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(4,3,2);self.pa=self.pb=self.turns=0;self.sealed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stock,self.pa,self.pb,self.turns,self.sealed),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.stock,self.pa,self.pb,self.turns,self.sealed=s
  elif a==6:
   if (self.stock,self.pa,self.pb,self.turns,self.sealed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
