"""a066 Strobe Swarm -- choose flash times that reveal several motion periods."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,NIGHT,FIELD,BUG_A,BUG_B,BUG_C,FLASH,NET,SAMPLE,BAD=10,8,9,12,14,6,11,13,4,15
LEVELS=[
 {"name":"First Flash","seq":(2,)},{"name":"Advance Clock","seq":(1,2)},
 {"name":"Different Periods","seq":(1,1,2,3)},{"name":"Avoid Blind Phase","seq":(4,1,2,3,3)},
 {"name":"Place Intercept","seq":(1,2,4,1,2,3,3)},{"name":"Strobe Swarm","seq":(1,4,2,1,1,2,3,4,3,2)},
]
def advance(s,a):
 phases,clock,flashes,net,step,intercept,history,snapshot=s;p=list(phases)
 if a==1:clock=(clock+step)%12;p=[(p[i]+i+1)%12 for i in range(3)];history=(history+(1,))[-8:]
 elif a==2:flashes=(flashes+((clock,tuple(p)),))[-4:];history=(history+(2,))[-8:]
 elif a==3:net=(net+1)%12;intercept=sum(int(x==net) for x in p);history=(history+(3,))[-8:]
 elif a==4:step=1+step%4;clock=(clock+step)%12;p=[(p[i]+step*(i+1))%12 for i in range(3)];history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(p),clock,flashes,net,step,intercept,history)
 return tuple(p),clock,flashes,net,step,intercept,history,snapshot
for x in LEVELS:
 s=((0,3,7),0,(),0,1,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=NIGHT
  colors=(BUG_A,BUG_B,BUG_C)
  for i,p in enumerate(g.phases):
   y=13+i*14;f[y:y+8,7:57]=FIELD;x=8+p*4;f[y-2:y+10,x:x+5]=colors[i]
  nx=8+g.net*4;f[8:53,nx:nx+3]=NET
  for i,_ in enumerate(g.flashes):f[54:58,8+i*11:17+i*11]=FLASH
  f[7:10,8:8+g.sample_step*9]=SAMPLE
  for i in range(g.intercept):f[5:9,45+i*5:49+i*5]=NET
  if g.bad:f[1:4,18:46]=BAD
  return f
class A066(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a066",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.phases,self.clock,self.flashes,self.net,self.sample_step,self.intercept,self.history,self.snapshot=((0,3,7),0,(),0,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.phases,self.clock,self.flashes,self.net,self.sample_step,self.intercept,self.history,self.snapshot=advance((self.phases,self.clock,self.flashes,self.net,self.sample_step,self.intercept,self.history,self.snapshot),a)
  elif a==6:
   if (self.phases,self.clock,self.flashes,self.net,self.sample_step,self.intercept,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
