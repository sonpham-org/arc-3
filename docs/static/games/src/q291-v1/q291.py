"""q291 Aurora Ledger -- conserve crystal stock through a hysteretic curtain sweep."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,CURTAIN,CRYSTAL,STOCK,CONTROL,DIRECTION,GOAL,BAD=11,10,15,14,12,9,6,0,8
LEVELS=[{"name":"First Transfer","plan":(1,4)},{"name":"Return Sweep","plan":(2,1,4)},{"name":"Conserved Curtain","plan":(3,4,2,1)},{"name":"Hysteresis Loop","plan":(1,4,4,2,3)},{"name":"Global Aurora","plan":(2,1,4,3,4,2)},{"name":"Aurora Ledger","plan":(3,1,4,2,4,3,1)}]
def advance(s,a):
 stock,control,direction,history=s;stock=list(stock);history=list(history)
 if a in (1,2,3):
  src=a-1;dst=(a+control)%3
  if stock[src]:stock[src]-=1;stock[dst]+=1
 elif a==4:
  control=(control+direction)%3
  if control in (0,2):direction=-direction
  stock=stock[1:]+stock[:1];history.append((control,direction))
 return tuple(stock),control,direction,tuple(history)
def target(x):
 s=((4,3,2),0,1,())
 for a in x["plan"]:s=advance(s,a)
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=SKY;f[8:17,8:56]=CURTAIN
  for i,v in enumerate(g.stock):x=9+i*18;f[22:36,x:x+12]=CRYSTAL;f[39:42,x:x+v*3]=STOCK
  f[47:50,8:8+g.control*14]=CONTROL;f[53:56,8:8+(g.direction+1)*12]=DIRECTION;f[58:60,8:8+sum(g.stock)*3]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q291(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q291",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stock=(4,3,2);self.control=0;self.direction=1;self.history=()
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4):self.stock,self.control,self.direction,self.history=advance((self.stock,self.control,self.direction,self.history),a)
  elif a==5:pass
  elif a==6:
   if (self.stock,self.control,self.direction,self.history)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
