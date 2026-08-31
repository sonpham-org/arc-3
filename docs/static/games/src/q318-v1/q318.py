"""q318 Escapement Ledger -- conserve weight stock while diagnosing a hidden fault."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,WEIGHT,STOCK,DIAG,PHASE,GOAL,BAD=3,10,9,14,6,11,4,7,15
LEVELS=[{"name":"First Transfer","fault":1,"plan":(1,4)},{"name":"Faulted Gear","fault":2,"plan":(2,1,4)},{"name":"Conserved Weight","fault":3,"plan":(3,4,2,1)},{"name":"Exclusive Ledger","fault":2,"plan":(1,4,3,2,5)},{"name":"Global Diagnosis","fault":3,"plan":(2,1,4,3,4,2)},{"name":"Escapement Ledger","fault":1,"plan":(3,1,4,2,4,3,1,5)}]
def advance(s,a,x):
 stock,phase,diagnostic,integrated=s;stock=list(stock)
 if a in (1,2,3):
  src=a-1;dst=(src+phase+x["fault"])%3
  if stock[src]:stock[src]-=1;stock[dst]+=1
 elif a==4:diagnostic=(x["fault"],tuple(stock));phase=(phase+1)%3;stock=stock[1:]+stock[:1]
 elif a==5:integrated=(sum((i+1)*v for i,v in enumerate(stock))+x["fault"]+phase)%7
 return tuple(stock),phase,diagnostic,integrated
def target(x):
 s=((4,3,2),0,None,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=TOWER
  for i,v in enumerate(g.stock):x=8+i*18;f[9:35,x:x+14]=GEAR;f[14:28,x+4:x+10]=WEIGHT-i;f[39:42,x:x+v*3]=STOCK
  f[48:51,8:20]=DIAG if g.diagnostic else GEAR;f[53:56,8:11+g.phase*14]=PHASE;f[58:60,48:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q318(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q318",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(4,3,2);self.phase=0;self.diagnostic=None;self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.stock,self.phase,self.diagnostic,self.integrated=advance((self.stock,self.phase,self.diagnostic,self.integrated),a,x)
  elif a==6:
   if (self.stock,self.phase,self.diagnostic,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
