"""q292 Tide Ledger -- conserve shell stock before sealing one irreversible exchange."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,CURRENT,SHELL,STOCK,SEAL,GOAL,BAD=3,9,10,14,5,11,7,15
LEVELS=[{"name":"First Exchange","plan":(1,5)},{"name":"Reverse Channel","plan":(2,1,4,5)},{"name":"Global Stock","plan":(3,4,2,1,5)},{"name":"One-Way Gate","plan":(1,4,3,2,5)},{"name":"Conserved Return","plan":(2,1,4,3,4,2,5)},{"name":"Tide Ledger","plan":(3,1,4,2,4,3,1,5)}]
def advance(s,a):
 stock,current,direction,history,sealed=s;stock=list(stock);history=list(history)
 if sealed:return None
 if a in (1,2,3):
  src=a-1;dst=(src+direction+current)%3
  if stock[src]:stock[src]-=1;stock[dst]+=1
 elif a==4:
  current=(current+direction)%3
  if current in (0,2):direction=-direction
  stock=stock[1:]+stock[:1];history.append((current,direction))
 elif a==5:sealed=True;history.append(tuple(stock))
 return tuple(stock),current,direction,tuple(history),sealed
def target(x):
 s=((4,3,2),0,1,(),False)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN;f[8:15,8:56]=CURRENT
  for i,v in enumerate(g.stock):x=9+i*18;f[20:36,x:x+12]=SHELL-i;f[39:42,x:x+v*3]=STOCK
  f[48:51,8:11+g.current*14]=CURRENT;f[54:57,8:20]=SEAL if g.sealed else GOAL;f[58:60,8:35]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q292(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q292",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(4,3,2);self.current=0;self.direction=1;self.history=();self.sealed=False
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.stock,self.current,self.direction,self.history,self.sealed),a)
   if s is None:self.bad=True;self.lose()
   else:self.stock,self.current,self.direction,self.history,self.sealed=s
  elif a==6:
   if (self.stock,self.current,self.direction,self.history,self.sealed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
