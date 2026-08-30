"""q312 Semaphore Ledger -- conserve global stock while testing two miniature relays."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CLIFF,FLAG,STOCK,BEAM,TESTA,TESTB,POLICY,BAD=12,1,15,14,10,6,9,11,8
LEVELS=[
 {"name":"First Relay","plan":(1,4)},
 {"name":"Second Miniature","plan":(2,5,1)},
 {"name":"Global Transfer","plan":(3,1,4,2)},
 {"name":"Occluded Beam","plan":(2,4,3,5,1)},
 {"name":"Dual Test","plan":(1,3,4,2,5,3)},
 {"name":"Semaphore Ledger","plan":(3,2,4,1,5,2,3,4)}]
def advance(s,a):
 stock,ta,tb,policy=s;stock=list(stock)
 if a in (1,2,3):
  src=a-1;dst=a%3
  if stock[src]:stock[src]-=1;stock[dst]+=1
 elif a==4:
  ta=(ta+(stock[0]-stock[2]))%4;stock[0],stock[1]=stock[1],stock[0]
 elif a==5:
  tb=(tb+(stock[1]+stock[2]))%4;stock[1],stock[2]=stock[2],stock[1]
 policy=(ta+2*tb+stock[0])%4
 return tuple(stock),ta,tb,policy
def target(x):
 s=((4,3,2),0,0,0)
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[35:60,3:61]=CLIFF
  for i,v in enumerate(g.stock):
   x=9+i*18;f[8:39,x:x+3]=BEAM;f[9+i*5:18+i*5,x+3:x+13]=FLAG;f[42:45,x:x+v*2]=STOCK
  f[48:51,7:7+g.ta*12]=TESTA;f[52:55,7:7+g.tb*12]=TESTB;f[56:59,7:7+g.policy*12]=POLICY
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q312(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.stock=(4,3,2);self.ta=self.tb=self.policy=0;self.bad=False;self.target=target(LEVELS[0])
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q312",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.stock=(4,3,2);self.ta=self.tb=self.policy=0;self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.stock,self.ta,self.tb,self.policy=advance((self.stock,self.ta,self.tb,self.policy),a)
  elif a==6:
   if (self.stock,self.ta,self.tb,self.policy)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
