"""q642 Semaphore Sandbox -- probe two signal copies before one irreversible policy commit."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,CLIFF,FLAG,BEAM,COPY,EVIDENCE,GOAL,BAD=6,11,4,14,9,7,12,13,15
LEVELS=[{"name":"First Copy","seq":(1,3)},{"name":"Second Copy","seq":(2,3,4)},{"name":"Occluded Result","seq":(1,3,4,2,3)},{"name":"Policy Contrast","seq":(2,1,3,4,1,3)},{"name":"Two Miniatures","seq":(1,2,3,4,2,2,3)},{"name":"Semaphore Sandbox","seq":(2,1,3,4,1,2,3,4,2,3)}]
def advance(s,a):
 main,copies,active,beam,evidence,commit=s;cp=[list(x) for x in copies]
 if a==1:cp[active][0]=(cp[active][0]+1+beam)%5;beam=(beam+1)%4
 elif a==2:cp[active][1]=(cp[active][1]+2+beam)%5;beam=(beam+2)%4
 elif a==3:evidence=evidence+((active,tuple(cp[active]),beam),)
 elif a==4:active^=1;cp[active]=list(main);beam=(beam+active)%4
 elif a==5:main=tuple(cp[active]);commit=(main,active,beam,evidence[-4:])
 return tuple(main),(tuple(cp[0]),tuple(cp[1])),active,beam,evidence,commit
for x in LEVELS:
 s=((0,2),((0,2),(0,2)),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD;f[7:31,7:29]=CLIFF;f[7:31,35:57]=COPY
  for side,vals in enumerate(g.copies):
   ox=9+side*28
   for i,v in enumerate(vals):f[12+i*10:19+i*10,ox:ox+15]=BEAM;f[14+i*10:17+i*10,ox+2:ox+4+v*2]=FLAG if side==g.active else COPY
  for i,(_,vals,z) in enumerate(g.evidence[-4:]):x=8+i*12;f[36:42,x:x+9]=EVIDENCE;f[43:46,x:x+2+sum(vals)%6]=BEAM
  f[51:55,8:8+g.beam*12+9]=FLAG
  if g.commit:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q642(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q642",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.main=(0,2);self.copies=((0,2),(0,2));self.active=self.beam=0;self.evidence=();self.commit=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.main,self.copies,self.active,self.beam,self.evidence,self.commit=advance((self.main,self.copies,self.active,self.beam,self.evidence,self.commit),a)
  elif a==6:
   if (self.main,self.copies,self.active,self.beam,self.evidence,self.commit)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
