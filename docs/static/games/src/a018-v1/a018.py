"""a018 Reversed Joint -- calibrate two joint mappings before threading an arm."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,CELL,ARM,JOINT,SOCKET,TRACE,CONTACT,GOAL,BAD=7,10,14,8,11,6,12,13,15
LEVELS=[{"name":"First Joint","seq":(1,3)},{"name":"Second Joint","seq":(2,3)},{"name":"Reversed Direction","seq":(1,2,3)},{"name":"Zero Shift","seq":(4,2,1,3)},{"name":"Narrow Socket","seq":(2,3,1,4,2,1,3)},{"name":"Reversed Joint","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 angles,reverse,zero,tests,contacts,threaded=s;v=list(angles)
 if a==1:v[0]=(v[0]+(-1 if reverse==0 else 1))%8
 elif a==2:v[1]=(v[1]+(-1 if reverse==1 else 1))%8
 elif a==3:end=((v[0]+zero[0])%8,(v[0]+v[1]+sum(zero))%8);tests=tests+((tuple(v),end),);contacts+=int(end[0] in (0,7))
 elif a==4:zero=(zero[1],(zero[0]+1)%4);reverse^=1
 elif a==5:threaded=(tuple(v),reverse,zero,tests[-4:],contacts)
 return tuple(v),reverse,zero,tests,contacts,threaded
for x in LEVELS:
 s=((0,0),1,(1,2),(),0,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CELL;f[8:56,47:56]=SOCKET
  x1=12+g.angles[0]*4;y1=31-g.angles[0]*2;x2=min(46,x1+g.angles[1]*3);y2=31+g.angles[1]*2
  f[29:34,8:x1+1]=ARM;f[max(7,y1-2):min(57,y1+3),x1:x2+1]=ARM;f[26:37,x1-4:x1+5]=JOINT;f[max(7,y2-3):min(57,y2+4),max(7,x2-3):min(57,x2+4)]=JOINT
  f[39:43,8:28]=ARM
  for i,_ in enumerate(g.tests[-4:]):f[43:49,8+i*10:16+i*10]=TRACE
  f[52:56,8:8+min(5,g.contacts)*9]=CONTACT
  if g.threaded:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A018(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a018",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.angles=(0,0);self.reverse=1;self.zero=(1,2);self.tests=();self.contacts=0;self.threaded=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.angles,self.reverse,self.zero,self.tests,self.contacts,self.threaded=advance((self.angles,self.reverse,self.zero,self.tests,self.contacts,self.threaded),a)
  elif a==6:
   if (self.angles,self.reverse,self.zero,self.tests,self.contacts,self.threaded)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
