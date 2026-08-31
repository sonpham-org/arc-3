"""q316 Crossing Ledger -- conserve passengers across capped docks and partial controllers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,RIVER,DOCK,PASSENGER,STOCK,MARK,CONTROL,GOAL,BAD=8,10,9,14,5,11,2,7,15
LEVELS=[{"name":"First Transfer","capacity":5,"plan":(1,3)},{"name":"Remote Stock","capacity":5,"plan":(2,3,4,1)},{"name":"Conserved Fare","capacity":6,"plan":(1,2,3,4,2,3)},{"name":"Split Ledger","capacity":6,"plan":(2,1,3,4,1,2)},{"name":"Capacity Return","capacity":7,"plan":(1,3,4,2,1,3,5)},{"name":"Crossing Ledger","capacity":7,"plan":(2,1,3,4,1,2,3,5)}]
def advance(s,a,x):
 stock,controller,marks,integrated=s;stock=list(stock);marks=list(marks);cap=x["capacity"]
 if a in (1,2):
  src=(controller+a-1)%3;dst=(src+controller+1)%3
  if stock[src] and stock[dst]<cap:stock[src]-=1;stock[dst]+=1
 elif a==3:marks[controller]=(stock[controller]+stock[(controller+1)%3])%5
 elif a==4:controller=1-controller
 elif a==5:integrated=(marks[0]+marks[1]+stock[2])%7
 return tuple(stock),controller,tuple(marks),integrated
def target(x):
 s=((4,3,2),0,(0,0),0)
 for a in x["plan"]:s=advance(s,a,x)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;x=LEVELS[g.level_index];f[:,:]=BG;f[4:60,4:60]=RIVER
  for i,v in enumerate(g.stock):px=8+i*18;f[9:37,px:px+14]=DOCK;f[31-v*4:36-v*4,px+4:px+10]=PASSENGER-i;f[40:43,px:px+v*3]=STOCK
  f[48:51,8:11+g.marks[0]*10]=MARK;f[52:55,8:11+g.marks[1]*10]=MARK;f[57:60,8:11+g.controller*22]=CONTROL;f[57:60,48:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q316(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q316",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(4,3,2);self.controller=0;self.marks=(0,0);self.integrated=0
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.stock,self.controller,self.marks,self.integrated=advance((self.stock,self.controller,self.marks,self.integrated),a,x)
  elif a==6:
   if (self.stock,self.controller,self.marks,self.integrated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
