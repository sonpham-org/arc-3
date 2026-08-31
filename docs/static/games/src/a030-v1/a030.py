"""a030 Ownership Flash -- propagate rotating control between sparse ownership markers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ARENA,BODY,SOCKET,OWNER,MARKER,TRACE,GOAL,BAD=9,10,14,11,12,6,5,13,15
LEVELS=[{"name":"Visible Owner","seq":(1,)},{"name":"Hidden Turn","seq":(2,1)},{"name":"Rotation Law","seq":(3,1,2)},{"name":"Fourth Marker","seq":(4,2,1,3)},{"name":"Three Bodies","seq":(2,3,1,4,2,1)},{"name":"Ownership Flash","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 positions,owner,turn,markers,history,synced=s;p=list(positions)
 if a==1:p[owner]=(p[owner]+1)%8;history=history+((owner,tuple(p),turn),);turn+=1;owner=(owner+1)%3
 elif a==2:p[owner]=(p[owner]+2)%8;history=history+((owner,tuple(p),turn),);turn+=1;owner=(owner+1)%3
 elif a==3:history=history+((owner,tuple(p),turn),);turn+=1;owner=(owner+2)%3
 elif a==4:markers=markers+((turn,owner),);turn+=1;owner=(owner+1)%3
 elif a==5:synced=(tuple(p),owner,turn,markers[-3:],history[-5:])
 return tuple(p),owner,turn,markers,history,synced
for x in LEVELS:
 s=((0,3,6),0,0,((0,0),),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ARENA
  for lane,p in enumerate(g.positions):y=9+lane*12;f[y:y+8,7:57]=SOCKET;x=8+p*6;f[y:y+8,x:x+6]=OWNER if lane==g.owner and g.turn%4==0 else BODY
  for i,(t,o) in enumerate(g.markers[-3:]):x=8+i*14;f[47:52,x:x+10]=MARKER;f[53:56,x:x+2+o*3]=OWNER
  if g.synced:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A030(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target_state=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a030",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.positions=(0,3,6);self.owner=self.turn=0;self.markers=((0,0),);self.history=();self.synced=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target_state=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.positions,self.owner,self.turn,self.markers,self.history,self.synced=advance((self.positions,self.owner,self.turn,self.markers,self.history,self.synced),a)
  elif a==6:
   if (self.positions,self.owner,self.turn,self.markers,self.history,self.synced)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
