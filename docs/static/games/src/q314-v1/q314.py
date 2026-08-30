"""q314 Tessera Ledger -- conserve mosaic stock through an interruptible seam macro."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TESSERA,SEAM,STOCK,PHASE,LATCH,GOAL,BAD=7,0,15,10,14,12,9,11,8
LEVELS=[{"name":"First Transfer","window":1,"period":4,"plan":(1,4,5)},{"name":"Joined Stock","window":2,"period":5,"plan":(2,1,4,4,5)},{"name":"Global Mosaic","window":3,"period":6,"plan":(3,2,1,4,4,4,5)},{"name":"Compressed Seam","window":2,"period":5,"plan":(1,3,2,4,4,5,4)},{"name":"Macro Ledger","window":4,"period":7,"plan":(2,1,3,4,4,4,4,5)},{"name":"Tessera Ledger","window":5,"period":8,"plan":(3,1,2,3,4,4,4,4,4,5,4)}]
def advance(s,a,x):
 stock,phase,latch,shift=s;stock=list(stock)
 if a in (1,2,3):
  src=a-1;dst=a%3
  if stock[src]:stock[src]-=1;stock[dst]+=1
 elif a==4:phase=(phase+1)%x["period"];stock=stock[1:]+stock[:1];shift=(shift+phase)%4
 elif a==5:
  if phase!=x["window"]:return None
  latch=True;stock.reverse()
 return tuple(stock),phase,latch,shift
def target(x):
 s=((4,3,2),0,False,0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=MOSAIC
  for i,v in enumerate(g.stock):x=8+i*18;f[9:15,x:x+13]=TESSERA-i;f[18:18+v*5,x:x+13]=STOCK
  f[45:49,7:7+g.phase*6]=PHASE;f[51:54,7:7+g.shift*12]=SEAM
  if g.latch:f[56:60,12:52]=LATCH
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q314(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.stock=(4,3,2);self.phase=self.shift=0;self.latch=self.bad=False;self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q314",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.stock=(4,3,2);self.phase=self.shift=0;self.latch=self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stock,self.phase,self.latch,self.shift),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.stock,self.phase,self.latch,self.shift=s
  elif a==6:
   if (self.stock,self.phase,self.latch,self.shift)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
