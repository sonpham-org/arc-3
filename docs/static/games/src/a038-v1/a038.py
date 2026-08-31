"""a038 Deque Ferry -- serve spatial requests using only front and back cargo access."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,HARBOR,FERRY,CARGO,FRONT,BACK,REQUEST,GOAL,BAD=7,10,8,14,11,12,6,13,15
LEVELS=[{"name":"Load Front","seq":(1,)},{"name":"Load Back","seq":(2,1)},{"name":"Serve Front","seq":(3,1,2)},{"name":"Serve Back","seq":(4,2,1,3)},{"name":"Interior Locked","seq":(2,3,1,4,2,1)},{"name":"Deque Ferry","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 cargo,next_cargo,requests,served,history,schedule=s;c=list(cargo);r=list(requests);out=list(served)
 if a==1:c.insert(0,next_cargo);next_cargo=(next_cargo+1)%8
 elif a==2:c.append(next_cargo);next_cargo=(next_cargo+1)%8
 elif a==3:
  if c:out.append(("front",c.pop(0),r.pop(0) if r else -1))
  history=history+((tuple(c),tuple(out)),)
 elif a==4:
  if c:out.append(("back",c.pop(),r.pop(0) if r else -1))
  history=history+((tuple(c),tuple(out)),)
 elif a==5:schedule=(tuple(c),next_cargo,tuple(r),tuple(out[-5:]),history[-4:])
 return tuple(c),next_cargo,tuple(r),tuple(out),history,schedule
for x in LEVELS:
 s=((),0,(2,5,1,6,3),(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=HARBOR;f[16:32,7:57]=FERRY
  f[1:4,8:28]=FRONT;f[1:4,32:52]=BACK
  for i,v in enumerate(g.cargo[-7:]):f[20:29,9+i*7:15+i*7]=FRONT if i==0 else BACK if i==len(g.cargo[-7:])-1 else CARGO
  for i,v in enumerate(g.requests[-5:]):f[38:43,8+i*10:16+i*10]=REQUEST
  for i,_ in enumerate(g.served[-4:]):f[48:53,8+i*12:17+i*12]=CARGO
  if g.schedule:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A038(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a038",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cargo=();self.next_cargo=0;self.requests=(2,5,1,6,3);self.served=self.history=();self.schedule=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cargo,self.next_cargo,self.requests,self.served,self.history,self.schedule=advance((self.cargo,self.next_cargo,self.requests,self.served,self.history,self.schedule),a)
  elif a==6:
   if (self.cargo,self.next_cargo,self.requests,self.served,self.history,self.schedule)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
