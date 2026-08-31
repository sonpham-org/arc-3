"""q668 Asterism Analogy -- transfer a cyclic star relation across unlike surfaces."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,FIELD,SOURCE,LINK,TARGET,PHASE,SURFACE,MAPPED,GOAL,BAD=5,9,11,10,14,6,7,12,13,15
LEVELS=[
 {"name":"One Rotation","pair":(1,3),"ops":(1,),"surface":0},
 {"name":"Changed Surface","pair":(0,4),"ops":(1,1),"surface":1},
 {"name":"Precessed Relation","pair":(2,6),"ops":(2,),"surface":1},
 {"name":"Cyclic Transfer","pair":(1,5),"ops":(1,2,1),"surface":2},
 {"name":"Hidden Appearance","pair":(3,7),"ops":(2,1,2,1),"surface":2},
 {"name":"Asterism Analogy","pair":(0,5),"ops":(1,2,2,1,2),"surface":1}]
def advance(s,a):
 pair,phase,mapped,surface,done=s;x,y=pair
 if a==1:pair=((x+1)%8,(y+1)%8)
 elif a==2:pair=(y,(x+phase+1)%8);phase=(phase+1)%4
 elif a==3:mapped=((pair[1]-pair[0])%8,phase)
 elif a==4:surface=(surface+1)%3
 elif a==5:
  if mapped is None:return None
  done=(mapped,surface)
 return pair,phase,mapped,surface,done
for x in LEVELS:x["plan"]=x["ops"]+(3,)+(4,)*x["surface"]+(5,)
def target(x):
 s=(x["pair"],0,None,0,None)
 for a in x["plan"]:s=advance(s,a);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD;f[8:34,7:29]=SOURCE;f[8:34,35:57]=TARGET
  for i in range(8):
   y=11+(i%4)*5;x=10+(i//4)*10;f[y:y+3,x:x+3]=GOAL if i in g.pair else LINK
   y2=11+(i%4)*5;x2=38+(i//4)*10;f[y2:y2+3,x2:x2+3]=MAPPED if g.mapped and i in g.mapped else SURFACE
  f[39:43,8:8+g.phase*11+7]=PHASE
  f[47:52,8:8+g.surface*15+10]=SURFACE
  if g.done:f[55:59,40:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q668(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q668",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pair=self.cfg["pair"];self.phase=self.surface=0;self.mapped=self.done=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.pair,self.phase,self.mapped,self.surface,self.done),a)
   if s is None:self.bad=True;self.lose()
   else:self.pair,self.phase,self.mapped,self.surface,self.done=s
  elif a==6:
   if (self.pair,self.phase,self.mapped,self.surface,self.done)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
