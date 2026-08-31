"""q320 Workbench Ledger -- conserve tool stock and return helper-bound loans."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BENCH,FIXTURE,TOOL,STOCK,HELPER,DEBT,SEAL,BAD=3,10,9,14,6,11,4,7,15
LEVELS=[{"name":"Borrowed Unit","plan":(1,4,5)},{"name":"Moved Stock","plan":(2,4,1,2,5)},{"name":"Third Bin","plan":(3,4,1,2,3,5)},{"name":"Two Ledgers","plan":(1,4,2,4,1,5,2,5)},{"name":"Crossed Loans","plan":(2,4,3,4,1,2,5,3,5)},{"name":"Workbench Ledger","plan":(1,4,2,4,3,4,3,5,2,5,1,5)}]
def advance(s,a):
 stock,selected,debt,turns,sealed=s;stock=list(stock);debt=list(debt)
 if a in (1,2,3):
  selected=a-1;dst=(selected+turns+1)%3
  if stock[selected]:stock[selected]-=1;stock[dst]+=1
  turns+=1
 elif a==4:stock[selected]+=1;debt[selected]+=1
 elif a==5:
  if not debt[selected] or not stock[selected]:return None
  stock[selected]-=1;debt[selected]-=1
  if not sum(debt):sealed=(tuple(stock),sum(stock),turns)
 return tuple(stock),selected,tuple(debt),turns,sealed
def target(x):
 s=((4,3,2),0,(0,0,0),0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BENCH
  for i,v in enumerate(g.stock):x=8+i*18;f[8:33,x:x+14]=FIXTURE;f[12:25,x+4:x+10]=TOOL-i;f[36:39,x:x+v*3]=STOCK;f[42:45,x:x+g.debt[i]*6]=DEBT
  f[49:52,8:24]=HELPER;f[55:58,44:56]=SEAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q320(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q320",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(4,3,2);self.selected=0;self.debt=(0,0,0);self.turns=0;self.sealed=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stock,self.selected,self.debt,self.turns,self.sealed),a)
   if s is None:self.bad=True;self.lose()
   else:self.stock,self.selected,self.debt,self.turns,self.sealed=s
  elif a==6:
   if (self.stock,self.selected,self.debt,self.turns,self.sealed)==self.target and sum(self.stock)==9:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
