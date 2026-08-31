"""q322 Tide Survey -- spend bounded samples before one irreversible route commitment."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,BASIN,LENS,CURRENT,SHELL,EVIDENCE,COST,COMMIT,BAD=4,10,14,9,12,6,11,7,15
LEVELS=[{"name":"One Sounding","budget":1,"plan":(1,5)},{"name":"Reverse Slice","budget":2,"plan":(2,4,1,5)},{"name":"Evidence Union","budget":3,"plan":(1,3,4,2,5)},{"name":"One-Way Route","budget":3,"plan":(2,4,3,1,5)},{"name":"Distinct Return","budget":4,"plan":(3,1,4,2,3,5)},{"name":"Tide Survey","budget":4,"plan":(1,4,3,2,4,1,5)}]
def advance(s,a):
 current,direction,evidence,cost,committed=s;evidence=list(evidence)
 if committed>=0:return None
 if a in (1,2,3):item=(a,current,(a+current+direction)%4);cost+=2 if item in evidence else 1;evidence.append(item)
 elif a==4:
  current=(current+direction)%3
  if current in (0,2):direction=-direction
 elif a==5:committed=(sum(v for _,_,v in evidence)+current+direction)%4
 return current,direction,tuple(evidence),cost,committed
def target(x):
 s=(0,1,(),0,-1)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=BASIN;f[8:14,8:56]=CURRENT
  for i in range(3):x=9+i*18;f[19:34,x:x+12]=LENS;f[24:29,x+4:x+8]=SHELL
  for i,(_,_,v) in enumerate(g.evidence[-6:]):f[38+i*3:40+i*3,8:11+v*11]=EVIDENCE
  f[54:57,8:11+g.cost*8]=COST;f[58:60,8:20]=COMMIT if g.committed>=0 else CURRENT
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q322(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q322",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.current=0;self.direction=1;self.evidence=();self.cost=0;self.committed=-1
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.current,self.direction,self.evidence,self.cost,self.committed),a)
   if s is None:self.bad=True;self.lose()
   else:
    self.current,self.direction,self.evidence,self.cost,self.committed=s
    if self.cost>x["budget"]:self.bad=True;self.lose()
  elif a==6:
   if (self.current,self.direction,self.evidence,self.cost,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
