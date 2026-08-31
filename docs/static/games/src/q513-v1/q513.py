"""q513 Murmuration Frame -- move locally in a rotating wake and audit one false parity view."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SKY,WAKE,BIRD,FRAME,VOTE0,VOTE1,AUDIT,BAD=10,9,1,13,12,6,14,11,15
LEVELS=[
 {"name":"Local Flight","moves":(1,),"liar":0},{"name":"Rotated Flight","moves":(2,1),"liar":1},
 {"name":"Wake Exchange","moves":(1,2,1,3),"liar":2},{"name":"Moving Frame","moves":(2,1,2,1,3),"liar":0},
 {"name":"Parity Flock","moves":(1,2,1,3,2,1),"liar":1},{"name":"Murmuration Frame","moves":(2,1,3,2,1,2,1),"liar":2}]
def moved(pos,rot,a):
 if a==1:pos=(pos+(1,2,-1,-2)[rot])%8
 elif a==2:rot=(rot+1)%4
 elif a==3:pos=(pos+4)%8
 return pos,rot
for x in LEVELS:
 pos=rot=0
 for a in x["moves"]:pos,rot=moved(pos,rot,a)
 x["goal"]=pos;x["plan"]=x["moves"]+(4,4,4,5)
def advance(s,a,x):
 pos,rot,votes,sensor,committed=s;votes=list(votes)
 if a in (1,2,3):pos,rot=moved(pos,rot,a);votes=[];sensor=0
 elif a==4:
  if len(votes)>=3:return None
  truth=(pos+rot)%2;votes.append(truth^int(sensor==x["liar"]));sensor+=1
 elif a==5:
  truth=(pos+rot)%2
  if pos!=x["goal"] or len(votes)!=3 or int(sum(votes)>=2)!=truth:return None
  committed=(pos,rot,truth)
 return pos,rot,tuple(votes),sensor,committed
def target(x):
 s=(0,0,(),0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SKY
  for i in range(8):
   x=8+(i%4)*12;y=9+(i//4)*14;f[y:y+7,x:x+8]=WAKE+(i%2)
  bx=10+(g.pos%4)*12;by=11+(g.pos//4)*14;f[by:by+4,bx:bx+4]=BIRD
  f[39:44,8:8+g.rot*12]=FRAME;f[49:54,8:28]=AUDIT
  for i,v in enumerate(g.votes):f[49:55,35+i*7:40+i*7]=VOTE1 if v else VOTE0
  if g.committed:f[56:60,39:56]=AUDIT
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q513(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q513",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=self.rot=self.sensor=0;self.votes=();self.committed=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.pos,self.rot,self.votes,self.sensor,self.committed),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.pos,self.rot,self.votes,self.sensor,self.committed=s
  elif a==6:
   if (self.pos,self.rot,self.votes,self.sensor,self.committed)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
