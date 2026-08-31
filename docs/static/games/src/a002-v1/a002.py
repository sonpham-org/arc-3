"""a002 Crosstalk Cart -- expose a shared control line through simultaneous calibration."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,RAIL,CART,CARGO,SIGNAL,INTERFERENCE,GOAL,BAD=1,10,8,14,11,6,12,13,15
LEVELS=[{"name":"Solo Motion","seq":(1,)},{"name":"Second Cart","seq":(2,1)},{"name":"Overlap Test","seq":(3,1,2)},{"name":"Calibration Mark","seq":(4,2,1,3)},{"name":"Shared Line","seq":(2,3,1,4,2,1)},{"name":"Crosstalk Cart","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 positions,shared,history,calibration,isolated=s;p=list(positions)
 if a==1:p[0]=(p[0]+1)%7;history=history+((1,tuple(p),False),)
 elif a==2:p[1]=(p[1]+2)%7;history=history+((2,tuple(p),False),)
 elif a==3:p[0]=(p[0]+1+shared)%7;p[1]=(p[1]+1+shared)%7;history=history+((3,tuple(p),True),);shared^=1
 elif a==4:calibration=calibration+((tuple(p),shared,history[-2:]),)
 elif a==5:isolated=(tuple(p),shared,history[-5:],calibration[-3:])
 return tuple(p),shared,history,calibration,isolated
for x in LEVELS:
 s=((0,3),1,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD
  for lane,p in enumerate(g.positions):y=10+lane*15;f[y:y+9,7:57]=RAIL;x=8+p*7;f[y+1:y+8,x:x+7]=CART;f[y+3:y+6,x+2:x+5]=CARGO
  for i,(a,_,cross) in enumerate(g.history[-4:]):x=8+i*12;f[39:45,x:x+9]=INTERFERENCE if cross else SIGNAL;f[46:49,x:x+2+a*2]=CART
  for i,_ in enumerate(g.calibration[-3:]):f[52:56,8+i*14:18+i*14]=SIGNAL
  if g.isolated:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A002(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a002",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions=(0,3);self.shared=1;self.history=self.calibration=();self.isolated=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.shared,self.history,self.calibration,self.isolated=advance((self.positions,self.shared,self.history,self.calibration,self.isolated),a)
  elif a==6:
   if (self.positions,self.shared,self.history,self.calibration,self.isolated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
